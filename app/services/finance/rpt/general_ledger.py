"""General ledger detail report context builder and CSV export."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance.gl.account import Account
from app.models.finance.gl.journal_entry import JournalEntry, JournalStatus
from app.models.finance.gl.journal_entry_line import JournalEntryLine
from app.services.common import coerce_uuid
from app.services.finance.rpt.common import (
    _build_csv,
    _format_currency,
    _format_date,
    _iso_date,
    _parse_date,
)


def general_ledger_context(
    db: Session,
    organization_id: str,
    account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    all_accounts_limit: int | None = 500,
) -> dict[str, Any]:
    """Get context for general ledger detail report."""
    org_id = coerce_uuid(organization_id)

    from_date = _parse_date(start_date)
    to_date = _parse_date(end_date)

    # Get accounts for dropdown
    accounts = db.scalars(
        select(Account)
        .where(
            Account.organization_id == org_id,
            Account.is_active.is_(True),
        )
        .order_by(Account.account_code)
    ).all()

    account_options = [
        {
            "account_id": str(acct.account_id),
            "account_code": acct.account_code if len(acct.account_code) < 20 else "",
            "account_name": acct.account_name,
        }
        for acct in accounts
    ]

    transactions: list[dict[str, Any]] = []
    selected_account = None
    running_balance = Decimal("0")
    all_accounts_selected = account_id == "all"
    all_accounts_requires_date_range = all_accounts_selected and not (
        from_date or to_date
    )
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    all_accounts_truncated = False

    if all_accounts_selected:
        selected_account = {
            "account_code": "All",
            "account_name": "accounts",
            "is_all_accounts": True,
        }

        if not all_accounts_requires_date_range:
            stmt = (
                select(JournalEntryLine, JournalEntry, Account)
                .join(
                    JournalEntry,
                    JournalEntry.journal_entry_id == JournalEntryLine.journal_entry_id,
                )
                .join(Account, Account.account_id == JournalEntryLine.account_id)
                .where(
                    JournalEntry.organization_id == org_id,
                    Account.organization_id == org_id,
                    JournalEntry.status == JournalStatus.POSTED,
                )
                .order_by(
                    Account.account_code,
                    JournalEntry.posting_date,
                    JournalEntry.journal_entry_id,
                )
            )
            if from_date:
                stmt = stmt.where(JournalEntry.posting_date >= from_date)
            if to_date:
                stmt = stmt.where(JournalEntry.posting_date <= to_date)
            if all_accounts_limit is not None:
                stmt = stmt.limit(all_accounts_limit + 1)

            lines = db.execute(stmt).all()
            if all_accounts_limit is not None and len(lines) > all_accounts_limit:
                all_accounts_truncated = True
                lines = lines[:all_accounts_limit]

            balances: dict[str, Decimal] = {}
            for line, entry, account in lines:
                debit = line.debit_amount_functional or Decimal("0")
                credit = line.credit_amount_functional or Decimal("0")
                total_debits += debit
                total_credits += credit

                account_key = str(account.account_id)
                current_balance = balances.get(account_key, Decimal("0"))
                if account.normal_balance.value == "DEBIT":
                    current_balance += debit - credit
                else:
                    current_balance += credit - debit
                balances[account_key] = current_balance

                transactions.append(
                    {
                        "date": _format_date(entry.posting_date),
                        "journal_number": entry.journal_number,
                        "account": f"{account.account_code} - {account.account_name}",
                        "description": line.description or entry.description,
                        "reference": entry.reference or "",
                        "debit": _format_currency(debit) if debit else "",
                        "credit": _format_currency(credit) if credit else "",
                        "balance": _format_currency(current_balance),
                    }
                )

    elif account_id:
        acct_id = coerce_uuid(account_id)
        selected_account = db.get(Account, acct_id)

        if selected_account and selected_account.organization_id != org_id:
            selected_account = None

        if selected_account:
            stmt = (
                select(JournalEntryLine, JournalEntry)
                .join(
                    JournalEntry,
                    JournalEntry.journal_entry_id == JournalEntryLine.journal_entry_id,
                )
                .where(
                    JournalEntryLine.account_id == acct_id,
                    JournalEntry.organization_id == org_id,
                    JournalEntry.status == JournalStatus.POSTED,
                )
                .order_by(JournalEntry.posting_date, JournalEntry.journal_entry_id)
            )
            if from_date:
                stmt = stmt.where(JournalEntry.posting_date >= from_date)
            if to_date:
                stmt = stmt.where(JournalEntry.posting_date <= to_date)

            lines = db.execute(stmt).all()

            for line, entry in lines:
                debit = line.debit_amount_functional or Decimal("0")
                credit = line.credit_amount_functional or Decimal("0")
                total_debits += debit
                total_credits += credit

                # Calculate running balance based on normal balance
                if selected_account.normal_balance.value == "DEBIT":
                    running_balance += debit - credit
                else:
                    running_balance += credit - debit

                transactions.append(
                    {
                        "date": _format_date(entry.posting_date),
                        "journal_number": entry.journal_number,
                        "description": line.description or entry.description,
                        "reference": entry.reference or "",
                        "debit": _format_currency(debit) if debit else "",
                        "credit": _format_currency(credit) if credit else "",
                        "balance": _format_currency(running_balance),
                    }
                )

    return {
        "start_date": _format_date(from_date) if from_date else "",
        "start_date_iso": _iso_date(from_date) if from_date else "",
        "end_date": _format_date(to_date) if to_date else "",
        "end_date_iso": _iso_date(to_date) if to_date else "",
        "period_label": (
            f"{_format_date(from_date)} to {_format_date(to_date)}"
            if from_date and to_date
            else f"From {_format_date(from_date)}"
            if from_date
            else f"Through {_format_date(to_date)}"
            if to_date
            else "All dates"
        ),
        "account_id": account_id,
        "accounts": account_options,
        "selected_account": (
            selected_account
            if isinstance(selected_account, dict)
            else {
                "account_code": selected_account.account_code,
                "account_name": selected_account.account_name,
                "is_all_accounts": False,
            }
            if selected_account
            else None
        ),
        "transactions": transactions,
        "ending_balance": _format_currency(running_balance),
        "total_debits": _format_currency(total_debits),
        "total_credits": _format_currency(total_credits),
        "all_accounts_selected": all_accounts_selected,
        "all_accounts_requires_date_range": all_accounts_requires_date_range,
        "all_accounts_truncated": all_accounts_truncated,
        "all_accounts_row_limit": all_accounts_limit,
    }


def export_general_ledger_csv(
    organization_id: str,
    db: Session,
    account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Export general ledger as CSV."""
    ctx = general_ledger_context(
        db,
        organization_id,
        account_id,
        start_date,
        end_date,
        all_accounts_limit=None,
    )
    is_all_accounts = bool(ctx.get("all_accounts_selected"))
    headers = ["Date", "Journal #"]
    if is_all_accounts:
        headers.append("Account")
    headers.extend(["Description", "Reference", "Debit", "Credit", "Balance"])

    rows = []
    for txn in ctx.get("transactions", []):
        row = [txn["date"], txn["journal_number"]]
        if is_all_accounts:
            row.append(txn.get("account", ""))
        row.extend(
            [
                txn["description"],
                txn["reference"],
                txn["debit"],
                txn["credit"],
                txn["balance"],
            ]
        )
        rows.append(row)
    return _build_csv(headers, rows)
