from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

from sqlalchemy import text

from ._types import (
    BankReconcileResult,
    BulkReconcileResult,
    PaystackReconcileResult,
)

logger = logging.getLogger(__name__)


class BankReconciliationMixin:
    """Non-Paystack bank reconciliation, bulk matching, and all-banks orchestrator."""

    # Provided by other mixins at runtime
    db: Any
    organization_id: UUID

    # These methods will be provided by ReconciliationMixin (which inherits us)
    reconcile_paystack_payments: Any

    def reconcile_bank_payments(
        self,
        bank_account_ids: list[UUID],
        bank_name: str = "Bank",
        dry_run: bool = False,
    ) -> BankReconcileResult:
        """Reconcile Splynx payments with bank statement lines."""
        logger.info(
            "Starting %s payment reconciliation (dry_run=%s)",
            bank_name,
            dry_run,
        )

        result: BankReconcileResult = {
            "bank_name": bank_name,
            "matched_by_date_amount": 0,
            "matched_by_customer": 0,
            "ambiguous_matches": 0,
            "unmatched_payments": 0,
            "unmatched_statements": 0,
            "total_matched_amount": Decimal("0"),
            "errors": [],
        }

        if not bank_account_ids:
            result["errors"].append("No bank account IDs provided")
            return result

        payments = self.db.execute(
            text("""
                SELECT
                    cp.payment_id,
                    cp.customer_id,
                    cp.payment_date,
                    cp.amount
                FROM ar.customer_payment cp
                WHERE cp.organization_id = :org_id
                  AND cp.correlation_id LIKE 'splynx-pmt-%%'
                  AND cp.bank_account_id = ANY(:account_ids)
            """),
            {
                "org_id": self.organization_id,
                "account_ids": bank_account_ids,
            },
        ).fetchall()

        logger.info(
            "Found %d Splynx payments for %s",
            len(payments),
            bank_name,
        )

        statement_lines = self.db.execute(
            text("""
                SELECT
                    bsl.line_id,
                    bsl.transaction_date,
                    bsl.amount
                FROM banking.bank_statement_lines bsl
                JOIN banking.bank_statements bs
                  ON bsl.statement_id = bs.statement_id
                WHERE bs.organization_id = :org_id
                  AND bs.bank_account_id = ANY(:account_ids)
                  AND bsl.transaction_type = 'credit'
                  AND bsl.is_matched = false
            """),
            {
                "org_id": self.organization_id,
                "account_ids": bank_account_ids,
            },
        ).fetchall()

        logger.info(
            "Found %d unmatched statement lines for %s",
            len(statement_lines),
            bank_name,
        )

        if not statement_lines:
            result["unmatched_payments"] = len(payments)
            result["errors"].append(
                f"No unmatched bank statement lines for {bank_name}"
            )
            return result

        matched_payment_ids: set[UUID] = set()
        matched_line_ids: set[UUID] = set()

        line_index: dict[tuple[object, int], list[UUID]] = {}
        for line in statement_lines:
            amount_cents = int(line.amount * 100)
            key = (line.transaction_date, amount_cents)
            if key not in line_index:
                line_index[key] = []
            line_index[key].append(line.line_id)

        ambiguous_payments: list[Any] = []
        for payment in payments:
            amount_cents = int(payment.amount * 100)
            key = (payment.payment_date, amount_cents)
            if key in line_index and line_index[key]:
                available = [
                    lid for lid in line_index[key] if lid not in matched_line_ids
                ]
                if len(available) == 1:
                    line_id = available[0]
                    matched_payment_ids.add(payment.payment_id)
                    matched_line_ids.add(line_id)
                    result["matched_by_date_amount"] += 1
                    result["total_matched_amount"] += payment.amount
                    if not dry_run:
                        self._mark_line_matched(
                            line_id,
                            f" [Matched to Splynx payment "
                            f"{payment.payment_id} by date+amount]",
                        )
                elif len(available) > 1:
                    ambiguous_payments.append(payment)

        logger.info(
            "Tier 1 (%s): %d matched by date+amount, %d ambiguous",
            bank_name,
            result["matched_by_date_amount"],
            len(ambiguous_payments),
        )

        # Tier 2: Customer-based
        customer_groups: dict[tuple[UUID, object, int], list[Any]] = defaultdict(list)
        for payment in ambiguous_payments:
            if payment.payment_id in matched_payment_ids:
                continue
            amount_cents = int(payment.amount * 100)
            ckey = (
                payment.customer_id,
                payment.payment_date,
                amount_cents,
            )
            customer_groups[ckey].append(payment)

        for (
            _cid,
            pay_date,
            amount_cents,
        ), group_payments in customer_groups.items():
            if len(group_payments) != 1:
                result["ambiguous_matches"] += len(group_payments)
                continue

            payment = group_payments[0]
            if payment.payment_id in matched_payment_ids:
                continue

            key = (pay_date, amount_cents)
            if key in line_index:
                available = [
                    lid for lid in line_index[key] if lid not in matched_line_ids
                ]
                if available:
                    line_id = available[0]
                    matched_payment_ids.add(payment.payment_id)
                    matched_line_ids.add(line_id)
                    result["matched_by_customer"] += 1
                    result["total_matched_amount"] += payment.amount
                    if not dry_run:
                        self._mark_line_matched(
                            line_id,
                            f" [Matched to Splynx payment "
                            f"{payment.payment_id} by customer+date+amount]",
                        )
                else:
                    result["ambiguous_matches"] += 1
            else:
                result["ambiguous_matches"] += 1

        result["unmatched_payments"] = max(0, len(payments) - len(matched_payment_ids))
        result["unmatched_statements"] = max(
            0,
            len(statement_lines) - len(matched_line_ids),
        )

        if not dry_run:
            self.db.flush()

        logger.info(
            "%s reconciliation complete: %d by date+amount, %d by customer, %d ambiguous",
            bank_name,
            result["matched_by_date_amount"],
            result["matched_by_customer"],
            result["ambiguous_matches"],
        )

        return result

    # -----------------------------------------------------------------
    # Bulk payment reconciliation
    # -----------------------------------------------------------------

    def reconcile_bulk_payments(
        self,
        bank_account_ids: list[UUID],
        bank_name: str = "Bank",
        dry_run: bool = False,
    ) -> BulkReconcileResult:
        """Match bulk payments where customer's multiple payments sum to one line."""
        logger.info(
            "Starting bulk payment reconciliation for %s (dry_run=%s)",
            bank_name,
            dry_run,
        )

        result: BulkReconcileResult = {
            "bank_name": bank_name,
            "bulk_matches": 0,
            "payments_matched": 0,
            "total_matched_amount": Decimal("0"),
            "errors": [],
        }

        if not bank_account_ids:
            return result

        matches = self.db.execute(
            text("""
                WITH customer_daily_totals AS (
                    SELECT
                        cp.customer_id,
                        cp.payment_date,
                        cp.bank_account_id,
                        SUM(cp.amount) as total_amount,
                        COUNT(*) as payment_count,
                        ARRAY_AGG(cp.payment_id) as payment_ids
                    FROM ar.customer_payment cp
                    WHERE cp.organization_id = :org_id
                      AND cp.correlation_id LIKE 'splynx-pmt-%%'
                      AND cp.bank_account_id = ANY(:account_ids)
                      AND cp.payment_date >= '2022-01-01'
                    GROUP BY cp.customer_id, cp.payment_date, cp.bank_account_id
                    HAVING COUNT(*) > 1
                ),
                unmatched_bank_lines AS (
                    SELECT
                        bsl.line_id,
                        bsl.transaction_date,
                        bsl.amount,
                        bs.bank_account_id
                    FROM banking.bank_statement_lines bsl
                    JOIN banking.bank_statements bs
                      ON bsl.statement_id = bs.statement_id
                    WHERE bs.organization_id = :org_id
                      AND bs.bank_account_id = ANY(:account_ids)
                      AND bsl.transaction_type = 'credit'
                      AND bsl.is_matched = false
                )
                SELECT
                    cdt.customer_id,
                    cdt.payment_date,
                    cdt.total_amount,
                    cdt.payment_count,
                    cdt.payment_ids,
                    ubl.line_id
                FROM customer_daily_totals cdt
                JOIN unmatched_bank_lines ubl
                    ON cdt.payment_date = ubl.transaction_date
                    AND ROUND(cdt.total_amount::numeric, 2)
                        = ROUND(ubl.amount::numeric, 2)
                    AND cdt.bank_account_id = ubl.bank_account_id
            """),
            {
                "org_id": self.organization_id,
                "account_ids": bank_account_ids,
            },
        ).fetchall()

        logger.info(
            "Found %d potential bulk payment matches for %s",
            len(matches),
            bank_name,
        )

        matched_line_ids: set[UUID] = set()

        for match in matches:
            if match.line_id in matched_line_ids:
                continue

            matched_line_ids.add(match.line_id)
            result["bulk_matches"] += 1
            result["payments_matched"] += match.payment_count
            result["total_matched_amount"] += match.total_amount

            if not dry_run:
                self._mark_line_matched(
                    match.line_id,
                    f" [Bulk match: {match.payment_count} "
                    "Splynx payments sum to this amount]",
                )

        if not dry_run:
            self.db.flush()

        logger.info(
            "%s bulk reconciliation: %d bank lines matched to %d payments (%s)",
            bank_name,
            result["bulk_matches"],
            result["payments_matched"],
            f"{result['total_matched_amount']:,.2f}",
        )

        return result

    # -----------------------------------------------------------------
    # All-banks orchestrator
    # -----------------------------------------------------------------

    def reconcile_all_banks(self, dry_run: bool = False) -> dict[str, Any]:
        """Reconcile Splynx payments for all bank accounts."""
        logger.info(
            "Starting reconciliation for all banks (dry_run=%s)",
            dry_run,
        )

        banks = self.db.execute(
            text("""
                SELECT DISTINCT
                    ba.bank_account_id,
                    ba.account_name,
                    ba.bank_name,
                    COUNT(cp.payment_id) as payment_count
                FROM ar.customer_payment cp
                JOIN banking.bank_accounts ba
                  ON cp.bank_account_id = ba.bank_account_id
                WHERE cp.organization_id = :org_id
                  AND cp.correlation_id LIKE 'splynx-pmt-%%'
                GROUP BY ba.bank_account_id, ba.account_name, ba.bank_name
                HAVING COUNT(cp.payment_id) > 0
                ORDER BY COUNT(cp.payment_id) DESC
            """),
            {"org_id": self.organization_id},
        ).fetchall()

        totals: dict[str, int | Decimal] = {
            "matched_by_date_amount": 0,
            "matched_by_customer": 0,
            "matched_by_reference": 0,
            "ambiguous_matches": 0,
            "total_matched_amount": Decimal("0"),
        }
        results: dict[str, Any] = {
            "banks": {},
            "totals": totals,
        }

        for bank in banks:
            bank_id = bank.bank_account_id
            bank_display = f"{bank.account_name} ({bank.bank_name})"
            bank_result: BankReconcileResult | PaystackReconcileResult

            if (
                "paystack" in bank.account_name.lower()
                or "paystack" in bank.bank_name.lower()
            ):
                bank_result = self.reconcile_paystack_payments(dry_run=dry_run)
                totals["matched_by_reference"] += bank_result.get(  # type: ignore[operator]
                    "matched_by_reference", 0
                )
            else:
                bank_result = self.reconcile_bank_payments(
                    bank_account_ids=[bank_id],
                    bank_name=bank_display,
                    dry_run=dry_run,
                )

            results["banks"][bank.account_name] = bank_result

            totals["matched_by_date_amount"] += bank_result.get(
                "matched_by_date_amount", 0
            )
            totals["matched_by_customer"] += bank_result.get("matched_by_customer", 0)
            totals["ambiguous_matches"] += bank_result.get("ambiguous_matches", 0)
            totals["total_matched_amount"] += bank_result.get(
                "total_matched_amount", Decimal("0")
            )

        all_bank_ids = [bank.bank_account_id for bank in banks]
        bulk_result = self.reconcile_bulk_payments(
            bank_account_ids=all_bank_ids,
            bank_name="All Banks",
            dry_run=dry_run,
        )

        results["bulk_matching"] = bulk_result
        totals["bulk_matches"] = bulk_result.get("bulk_matches", 0)
        totals["bulk_payments_matched"] = bulk_result.get("payments_matched", 0)
        totals["total_matched_amount"] += bulk_result.get(
            "total_matched_amount", Decimal("0")
        )

        return results

    # -----------------------------------------------------------------
    # Shared helper
    # -----------------------------------------------------------------

    def _mark_line_matched(self, line_id: UUID, note: str) -> None:
        """Mark a bank statement line as matched."""
        self.db.execute(
            text("""
                UPDATE banking.bank_statement_lines
                SET is_matched = true,
                    matched_at = :now,
                    notes = COALESCE(notes, '')
                            || E'\\n' || :note
                WHERE line_id = :line_id
            """),
            {
                "line_id": line_id,
                "now": datetime.now(tz=UTC),
                "note": note,
            },
        )
