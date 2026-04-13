"""
Mono Sync Service.

Synchronizes bank transactions from Mono Connect with bank statements
for reconciliation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

try:
    from datetime import UTC  # type: ignore
except ImportError:  # pragma: no cover
    UTC = timezone.utc

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.domain_settings import SettingDomain
from app.models.finance.banking import (
    BankAccount,
    BankAccountStatus,
    BankStatement,
    BankStatementLine,
    BankStatementStatus,
    StatementLineType,
)
from app.services.finance.banking.mono_client import (
    MonoClient,
    MonoConfig,
    MonoError,
)
from app.services.settings_spec import resolve_value

logger = logging.getLogger(__name__)


@dataclass
class MonoSyncResult:
    """Result of a Mono sync operation for one account."""

    success: bool
    bank_account_id: UUID | None = None
    statement_id: UUID | None = None
    transactions_synced: int = 0
    duplicates_skipped: int = 0
    total_credits: Decimal = Decimal("0")
    total_debits: Decimal = Decimal("0")
    message: str = ""
    errors: list[str] = field(default_factory=list)


class MonoSyncService:
    """
    Service for syncing Mono transactions with bank statements.

    Fetches transactions from linked Mono accounts and creates
    BankStatementLine entries for reconciliation.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_mono_config(self) -> MonoConfig:
        """Get Mono configuration from domain settings."""
        secret_key = resolve_value(self.db, SettingDomain.banking, "mono_secret_key")
        public_key = resolve_value(self.db, SettingDomain.banking, "mono_public_key")
        webhook_secret = resolve_value(
            self.db, SettingDomain.banking, "mono_webhook_secret"
        )

        if not secret_key or not public_key:
            raise ValueError("Mono Connect not configured — missing API keys")

        return MonoConfig(
            secret_key=str(secret_key),
            public_key=str(public_key),
            webhook_secret=str(webhook_secret) if webhook_secret else "",
        )

    def is_configured(self) -> bool:
        """Check if Mono Connect is enabled and configured."""
        enabled = resolve_value(self.db, SettingDomain.banking, "mono_enabled")
        if not enabled:
            return False
        try:
            self._get_mono_config()
            return True
        except ValueError:
            return False

    def link_account(
        self,
        organization_id: UUID,
        bank_account_id: UUID,
        code: str,
    ) -> dict:
        """Exchange a Mono widget code and link it to a bank account."""
        account = self.db.get(BankAccount, bank_account_id)
        if not account or account.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Bank account not found")

        if not self.is_configured():
            raise HTTPException(
                status_code=400,
                detail="Mono Connect is not configured",
            )

        if not code:
            raise HTTPException(
                status_code=400,
                detail="Authorization code is required",
            )

        config = self._get_mono_config()
        try:
            with MonoClient(config) as client:
                result = client.exchange_token(code)
        except MonoError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc

        account.mono_account_id = result.account_id
        self.db.flush()
        return {
            "status": "success",
            "message": "Bank account linked to Mono successfully",
            "data": {"mono_account_id": result.account_id},
        }

    def sync_account_by_id(
        self,
        organization_id: UUID,
        bank_account_id: UUID,
        *,
        days_back: int,
        user_id: UUID | None = None,
    ) -> dict:
        """Sync Mono transactions for a tenant-scoped bank account."""
        account = self.db.get(BankAccount, bank_account_id)
        if not account or account.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Bank account not found")

        if not account.mono_account_id:
            raise HTTPException(
                status_code=400,
                detail="Bank account is not linked to Mono",
            )

        to_date = date.today()
        from_date = to_date - timedelta(days=days_back)
        result = self.sync_account(account, from_date, to_date, user_id)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.message)

        return {
            "status": "success",
            "message": result.message,
            "data": {
                "transactions_synced": result.transactions_synced,
                "duplicates_skipped": result.duplicates_skipped,
                "total_credits": str(result.total_credits),
                "total_debits": str(result.total_debits),
            },
        }

    def process_webhook(self, header_secret: str, raw_body: bytes) -> dict:
        """Verify and process a Mono webhook payload."""
        if not header_secret:
            raise HTTPException(status_code=400, detail="Missing webhook secret")

        configured_secret = resolve_value(
            self.db,
            SettingDomain.banking,
            "mono_webhook_secret",
        )
        if not configured_secret:
            raise HTTPException(
                status_code=500,
                detail="Mono webhook secret not configured",
            )

        config = MonoConfig(webhook_secret=str(configured_secret))
        client = MonoClient(config)
        if not client.verify_webhook(header_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

        event = payload.get("event", "")
        event_data = payload.get("data", {})
        logger.info("Mono webhook received: event=%s", event)

        if event == "mono.events.account_updated":
            data_status = event_data.get("meta", {}).get("data_status", "")
            account_id = event_data.get("account", {}).get("id", "")
            logger.info(
                "Account updated: mono_id=%s, data_status=%s",
                account_id,
                data_status,
            )
        elif event == "mono.events.account_connected":
            logger.info("Account connected via webhook: %s", event_data)
        else:
            logger.info("Unhandled Mono event: %s", event)

        return {"status": "success", "message": f"Webhook {event} processed"}

    def get_linked_accounts(
        self, organization_id: UUID | None = None
    ) -> list[BankAccount]:
        """Get all bank accounts linked to Mono."""
        stmt = select(BankAccount).where(
            BankAccount.mono_account_id.isnot(None),
            BankAccount.status == BankAccountStatus.active,
        )
        if organization_id:
            stmt = stmt.where(BankAccount.organization_id == organization_id)
        return list(self.db.scalars(stmt).all())

    def sync_account(
        self,
        bank_account: BankAccount,
        from_date: date,
        to_date: date,
        user_id: UUID | None = None,
    ) -> MonoSyncResult:
        """
        Sync transactions from Mono for a single bank account.

        Fetches all transactions in the date range, deduplicates against
        existing statement lines, and creates new BankStatementLine entries.

        Args:
            bank_account: BankAccount with mono_account_id set.
            from_date: Start of the sync window.
            to_date: End of the sync window.
            user_id: User triggering the sync (None for scheduled tasks).

        Returns:
            MonoSyncResult with sync statistics.
        """
        if not bank_account.mono_account_id:
            return MonoSyncResult(
                success=False,
                bank_account_id=bank_account.bank_account_id,
                message="Bank account not linked to Mono",
            )

        config = self._get_mono_config()

        # Format dates for Mono API (DD-MM-YYYY)
        start_str = from_date.strftime("%d-%m-%Y")
        end_str = to_date.strftime("%d-%m-%Y")

        try:
            with MonoClient(config) as client:
                all_transactions = client.get_all_transactions(
                    bank_account.mono_account_id,
                    start=start_str,
                    end=end_str,
                )
        except MonoError as exc:
            logger.error(
                "Mono sync failed for account %s: %s",
                bank_account.bank_account_id,
                exc.message,
            )
            return MonoSyncResult(
                success=False,
                bank_account_id=bank_account.bank_account_id,
                message=f"Mono API error: {exc.message}",
                errors=[exc.message],
            )

        if not all_transactions:
            return MonoSyncResult(
                success=True,
                bank_account_id=bank_account.bank_account_id,
                message="No transactions found for the period",
            )

        # Get or create statement for this period
        statement = self._get_or_create_statement(
            account=bank_account,
            from_date=from_date,
            to_date=to_date,
            user_id=user_id,
        )

        # Get existing Mono transaction IDs to deduplicate
        existing_ids = self._get_existing_transaction_ids(bank_account.bank_account_id)

        # Process transactions
        count = 0
        duplicates = 0
        total_credits = Decimal("0")
        total_debits = Decimal("0")
        line_number = self._get_max_line_number(statement.statement_id)

        for txn in all_transactions:
            mono_txn_id = f"mono_{txn.id}"
            if mono_txn_id in existing_ids:
                duplicates += 1
                continue

            amount = txn.amount_major  # kobo → Naira
            is_credit = txn.type.lower() == "credit"
            line_type = (
                StatementLineType.credit if is_credit else StatementLineType.debit
            )

            line_number += 1
            line = BankStatementLine(
                line_id=uuid4(),
                statement_id=statement.statement_id,
                line_number=line_number,
                transaction_id=mono_txn_id,
                transaction_date=self._parse_date(txn.date),
                value_date=self._parse_date(txn.date),
                transaction_type=line_type,
                amount=amount,
                running_balance=txn.balance_major,
                description=txn.narration,
                reference=txn.narration,
                payee_payer="",
                is_matched=False,
                raw_data={
                    "mono_id": txn.id,
                    "mono_type": txn.type,
                    "mono_amount_kobo": txn.amount,
                    "mono_balance_kobo": txn.balance,
                    "mono_category": txn.category,
                    "mono_narration": txn.narration,
                    "import_source": "mono",
                },
                created_at=datetime.now(UTC),
            )
            self.db.add(line)
            count += 1

            if is_credit:
                total_credits += amount
            else:
                total_debits += amount

        # Update statement totals
        statement.total_credits += total_credits
        statement.total_debits += total_debits
        statement.total_lines += count
        statement.unmatched_lines += count
        if statement.closing_balance is not None:
            statement.closing_balance += total_credits - total_debits

        # Update bank account last statement info
        if count > 0:
            bank_account.last_statement_date = to_date
            if all_transactions and all_transactions[0].balance is not None:
                balance = all_transactions[0].balance_major
                if balance is not None:
                    bank_account.last_statement_balance = balance

        self.db.flush()

        logger.info(
            "Mono sync complete for %s: %d new, %d duplicates, credits=₦%s, debits=₦%s",
            bank_account.display_name,
            count,
            duplicates,
            f"{total_credits:,.2f}",
            f"{total_debits:,.2f}",
        )

        return MonoSyncResult(
            success=True,
            bank_account_id=bank_account.bank_account_id,
            statement_id=statement.statement_id,
            transactions_synced=count,
            duplicates_skipped=duplicates,
            total_credits=total_credits,
            total_debits=total_debits,
            message=(
                f"Synced {count} transactions "
                f"(₦{total_credits:,.2f} credits, ₦{total_debits:,.2f} debits)"
            ),
        )

    def sync_all_linked_accounts(
        self,
        days_back: int = 3,
        user_id: UUID | None = None,
    ) -> dict[str, object]:
        """
        Sync all Mono-linked bank accounts.

        Called by the Celery beat task on a schedule.

        Args:
            days_back: Number of days to look back for transactions.
            user_id: User triggering the sync.

        Returns:
            Dict with overall sync statistics.
        """
        from datetime import timedelta

        accounts = self.get_linked_accounts()
        if not accounts:
            return {
                "success": True,
                "accounts_synced": 0,
                "message": "No Mono-linked bank accounts found",
            }

        to_date = date.today()
        from_date = to_date - timedelta(days=days_back)

        results: list[MonoSyncResult] = []
        for account in accounts:
            try:
                result = self.sync_account(account, from_date, to_date, user_id)
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "Failed to sync Mono account %s", account.bank_account_id
                )
                results.append(
                    MonoSyncResult(
                        success=False,
                        bank_account_id=account.bank_account_id,
                        message=str(exc),
                        errors=[str(exc)],
                    )
                )

        total_synced = sum(r.transactions_synced for r in results)
        total_errors = sum(len(r.errors) for r in results)
        successful = sum(1 for r in results if r.success)

        return {
            "success": total_errors == 0,
            "accounts_synced": successful,
            "accounts_failed": len(results) - successful,
            "total_transactions": total_synced,
            "total_errors": total_errors,
            "errors": [e for r in results for e in r.errors],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_existing_transaction_ids(self, bank_account_id: UUID) -> set[str]:
        """Get all Mono transaction IDs already imported for this account."""
        return set(
            self.db.scalars(
                select(BankStatementLine.transaction_id)
                .join(
                    BankStatement,
                    BankStatementLine.statement_id == BankStatement.statement_id,
                )
                .where(
                    BankStatement.bank_account_id == bank_account_id,
                    BankStatementLine.transaction_id.isnot(None),
                    BankStatementLine.transaction_id.startswith("mono_"),
                )
            ).all()
        )

    def _get_max_line_number(self, statement_id: UUID) -> int:
        """Get the highest line number in a statement."""
        from sqlalchemy import func

        result = self.db.scalar(
            select(func.coalesce(func.max(BankStatementLine.line_number), 0)).where(
                BankStatementLine.statement_id == statement_id
            )
        )
        return int(result) if result else 0

    def _get_or_create_statement(
        self,
        account: BankAccount,
        from_date: date,
        to_date: date,
        user_id: UUID | None,
    ) -> BankStatement:
        """Get existing Mono statement or create new one for the period."""
        statement_number = (
            f"MONO-{from_date.strftime('%Y%m%d')}-{to_date.strftime('%Y%m%d')}"
        )

        existing = self.db.scalar(
            select(BankStatement).where(
                BankStatement.bank_account_id == account.bank_account_id,
                BankStatement.statement_number == statement_number,
            )
        )

        if existing:
            return existing

        # Get last statement's closing balance as opening balance
        last_statement = self.db.scalar(
            select(BankStatement)
            .where(BankStatement.bank_account_id == account.bank_account_id)
            .order_by(BankStatement.statement_date.desc())
        )
        opening_balance = (
            last_statement.closing_balance if last_statement else Decimal("0")
        )

        statement = BankStatement(
            statement_id=uuid4(),
            organization_id=account.organization_id,
            bank_account_id=account.bank_account_id,
            statement_number=statement_number,
            statement_date=to_date,
            period_start=from_date,
            period_end=to_date,
            opening_balance=opening_balance,
            closing_balance=opening_balance,
            total_credits=Decimal("0"),
            total_debits=Decimal("0"),
            currency_code=settings.default_functional_currency_code,
            status=BankStatementStatus.imported,
            import_source="mono",
            imported_at=datetime.now(UTC),
            imported_by=user_id,
            total_lines=0,
            matched_lines=0,
            unmatched_lines=0,
            created_at=datetime.now(UTC),
        )
        self.db.add(statement)
        self.db.flush()

        return statement

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse a Mono ISO 8601 date string to a date object."""
        if not date_str:
            return date.today()
        # Mono returns ISO 8601: "2023-12-14T00:02:00.500Z"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.date()
        except (ValueError, AttributeError):
            return date.today()
