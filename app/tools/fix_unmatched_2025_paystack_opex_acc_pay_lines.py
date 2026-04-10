"""
Fix remaining unmatched 2025 Paystack OPEX ACC-PAY statement lines.

Strategy:
- For Employee Payment Entries: post an "extra" expense reimbursement journal
  (debit employee payable, credit Paystack OPEX bank GL) keyed by ACC-PAY token,
  and match the bank statement line to that journal's bank line.
- For Supplier Payment Entries: post the synced SupplierPayment to GL, then match.

This is intended to clean up the last edge cases where ERPNext Payment Entries
have no child "references" rows but still carry a custom expense claim pointer,
or where an ACC-PAY line was an AP supplier payment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.models.expense.expense_claim import ExpenseClaim
from app.models.finance.gl.journal_entry import JournalEntry, JournalStatus, JournalType
from app.services.expense.expense_posting_adapter import ExpensePostingAdapter
from app.services.finance.gl.journal import JournalInput, JournalLineInput
from app.services.finance.posting.base import BasePostingAdapter

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
PAYSTACK_OPEX_BANK_ACCOUNT_ID = UUID("548e51bd-2171-429c-87d0-d0ff631ab75a")
ADMIN_PERSON_ID = UUID("c8e5f2ee-4f9f-46d0-a6c7-22e4f717a58b")

_ACC_PAY_RE = re.compile(r"(ACC-PAY-\d{4}-\d+(?:-\d+)?)")


@dataclass(frozen=True)
class Stats:
    scanned: int = 0
    employee_fixed: int = 0
    supplier_fixed: int = 0
    skipped_no_token: int = 0
    skipped_no_erp_doc: int = 0
    skipped_no_claim: int = 0
    failed: int = 0


def _extract_token(desc: str | None) -> str | None:
    if not desc:
        return None
    m = _ACC_PAY_RE.search(desc)
    return m.group(1) if m else None


def _resolve_expense_claim_name_from_payment_entry(pe: dict) -> str | None:
    refs = pe.get("references") or []
    for r in refs:
        if r.get("reference_doctype") == "Expense Claim" and r.get("reference_name"):
            return str(r["reference_name"])

    # Fallback for legacy/custom implementations (seen in ERPNext instance)
    for k in ("custom_expense_claim", "reference_no"):
        v = pe.get(k)
        if isinstance(v, str) and v.startswith("HR-EXP-"):
            return v
    return None


def _ensure_extra_reimbursement_journal(
    db,
    *,
    bank_gl_account_id: UUID,
    claim: ExpenseClaim,
    token: str,
    paid_on: date,
    amount: Decimal,
) -> JournalEntry:
    # Idempotency: reuse existing journal if we already posted it for this token.
    existing = db.scalar(
        select(JournalEntry).where(
            JournalEntry.organization_id == ORG_ID,
            JournalEntry.status == JournalStatus.POSTED,
            JournalEntry.correlation_id == token,
            JournalEntry.source_document_type == "EXPENSE_REIMBURSEMENT",
            JournalEntry.source_document_id == claim.claim_id,
        )
    )
    if existing:
        return existing

    payable_account_id = ExpensePostingAdapter._get_employee_payable_account(  # noqa: SLF001
        db, ORG_ID
    )
    if not payable_account_id:
        raise RuntimeError("Employee payable account not configured")

    journal_input = JournalInput(
        journal_type=JournalType.STANDARD,
        entry_date=paid_on,
        posting_date=paid_on,
        description=f"Expense Reimbursement (extra) {claim.claim_number} {token}",
        reference=token[:100],
        currency_code=settings.default_functional_currency_code,
        exchange_rate=Decimal("1.0"),
        lines=[
            JournalLineInput(
                account_id=payable_account_id,
                debit_amount=amount,
                credit_amount=Decimal("0"),
                debit_amount_functional=amount,
                credit_amount_functional=Decimal("0"),
                description=f"Expense reimbursement: {claim.claim_number}",
            ),
            JournalLineInput(
                account_id=bank_gl_account_id,
                debit_amount=Decimal("0"),
                credit_amount=amount,
                debit_amount_functional=Decimal("0"),
                credit_amount_functional=amount,
                description=f"Bank outflow: {token}",
            ),
        ],
        source_module="EXPENSE",
        source_document_type="EXPENSE_REIMBURSEMENT",
        source_document_id=claim.claim_id,
        correlation_id=token,
    )

    journal, err = BasePostingAdapter.create_and_approve_journal(
        db,
        ORG_ID,
        journal_input,
        ADMIN_PERSON_ID,
        error_prefix="Journal creation failed",
    )
    if err:
        raise RuntimeError(err.message)

    idempotency_key = f"{ORG_ID}:EXP:REIMB_EXTRA:{claim.claim_id}:{token}:post:v1"
    post = BasePostingAdapter.post_to_ledger(
        db,
        organization_id=ORG_ID,
        journal_entry_id=journal.journal_entry_id,
        posting_date=paid_on,
        idempotency_key=idempotency_key,
        source_module="EXPENSE",
        correlation_id=token,
        posted_by_user_id=ADMIN_PERSON_ID,
        success_message="Extra reimbursement posted",
    )
    if not post.success:
        raise RuntimeError(post.message)

    return journal


def main() -> None:
    print("ERPNext API sync is disabled. Use SQL-based sync tooling.")  # noqa: T201
    raise SystemExit(2)


if __name__ == "__main__":
    main()
