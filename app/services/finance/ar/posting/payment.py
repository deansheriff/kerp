"""
AR Payment Posting - Post customer payments to GL.

Transforms customer payments into journal entries with:
- Debit: Bank/Cash account
- Credit: AR Control account (reduce receivable)
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.finance.ar.customer import Customer
from app.models.finance.ar.payment_allocation import PaymentAllocation
from app.models.finance.banking.bank_account import BankAccount
from app.models.finance.gl.fiscal_period import FiscalPeriod
from app.models.finance.gl.journal_entry import JournalEntry, JournalStatus
from app.models.finance.gl.account import Account
from app.models.finance.gl.journal_entry import JournalType
from app.services.common import coerce_uuid
from app.services.finance.ar.posting.helpers import build_cash_vat_reclass_entries
from app.services.finance.ar.posting.result import ARPostingResult
from app.services.finance.gl.journal import (
    JournalInput,
    JournalLineInput,
)
from app.services.finance.posting.base import BasePostingAdapter
from app.services.finance.tax.tax_transaction import tax_transaction_service


def _resolve_bank_gl_account_id(
    db: Session,
    organization_id: UUID,
    bank_account_id: UUID,
) -> UUID | None:
    """
    Resolve payment bank account to a GL account ID.

    Supports both legacy storage patterns:
    - direct `gl.account.account_id`
    - `banking.bank_accounts.bank_account_id` (mapped via `gl_account_id`)
    """
    gl_account = db.get(Account, bank_account_id)
    if gl_account and gl_account.organization_id == organization_id:
        return bank_account_id

    bank_account = db.get(BankAccount, bank_account_id)
    if (
        bank_account
        and bank_account.organization_id == organization_id
        and bank_account.gl_account_id
    ):
        mapped_gl = db.get(Account, bank_account.gl_account_id)
        if mapped_gl and mapped_gl.organization_id == organization_id:
            return bank_account.gl_account_id

    return None


def post_vat_reclass_for_payment(
    db: Session,
    *,
    organization_id: UUID,
    payment,
    customer: Customer,
    posting_date: date,
    posted_by_user_id: UUID,
) -> ARPostingResult | None:
    """Post deferred-VAT reclass and cash-basis tax rows for an AR payment."""
    org_id = coerce_uuid(organization_id)
    pay_id = payment.payment_id
    user_id = coerce_uuid(posted_by_user_id)
    exchange_rate = payment.exchange_rate or Decimal("1.0")

    allocations = list(
        db.scalars(
            select(PaymentAllocation).where(PaymentAllocation.payment_id == pay_id)
        ).all()
    )
    reclass_entries, tax_payloads = build_cash_vat_reclass_entries(
        db, org_id, allocations
    )
    if not reclass_entries:
        return None

    existing_reclass_journal = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_module == "AR",
            JournalEntry.source_document_type == "CUSTOMER_PAYMENT_VAT_RECLASS",
            JournalEntry.source_document_id == pay_id,
            JournalEntry.status.notin_([JournalStatus.VOID, JournalStatus.REVERSED]),
        )
    )
    if existing_reclass_journal:
        return None

    grouped: dict[tuple[UUID, UUID], Decimal] = {}
    for row in reclass_entries:
        key = (
            row["deferred_account_id"],
            row["current_account_id"],
        )
        grouped[key] = grouped.get(key, Decimal("0")) + row["tax_amount"]

    reclass_lines: list[JournalLineInput] = []
    for (deferred_account_id, current_account_id), tax_amount in grouped.items():
        functional_tax = tax_amount * exchange_rate
        reclass_lines.append(
            JournalLineInput(
                account_id=deferred_account_id,
                debit_amount=tax_amount,
                credit_amount=Decimal("0"),
                debit_amount_functional=functional_tax,
                credit_amount_functional=Decimal("0"),
                description=f"Deferred VAT recognized on receipt {payment.payment_number}",
            )
        )
        reclass_lines.append(
            JournalLineInput(
                account_id=current_account_id,
                debit_amount=Decimal("0"),
                credit_amount=tax_amount,
                debit_amount_functional=Decimal("0"),
                credit_amount_functional=functional_tax,
                description=f"VAT payable recognized on receipt {payment.payment_number}",
            )
        )

    reclass_input = JournalInput(
        journal_type=JournalType.STANDARD,
        entry_date=payment.payment_date,
        posting_date=posting_date,
        description=f"AR VAT reclass {payment.payment_number} - {customer.legal_name}",
        reference=payment.reference or payment.payment_number,
        currency_code=payment.currency_code,
        exchange_rate=exchange_rate,
        lines=reclass_lines,
        source_module="AR",
        source_document_type="CUSTOMER_PAYMENT_VAT_RECLASS",
        source_document_id=pay_id,
        correlation_id=payment.correlation_id,
    )
    reclass_journal, reclass_error = BasePostingAdapter.create_and_approve_journal(
        db,
        org_id,
        reclass_input,
        user_id,
        error_prefix="VAT reclass journal creation failed",
    )
    if reclass_error:
        return ARPostingResult(success=False, message=reclass_error.message)

    reclass_result = BasePostingAdapter.post_to_ledger(
        db,
        organization_id=org_id,
        journal_entry_id=reclass_journal.journal_entry_id,
        posting_date=posting_date,
        idempotency_key=BasePostingAdapter.make_idempotency_key(
            org_id, "AR:PAY:VAT", pay_id, action="post"
        ),
        source_module="AR",
        correlation_id=payment.correlation_id,
        posted_by_user_id=user_id,
        success_message="VAT reclass posted successfully",
    )
    if not reclass_result.success:
        return ARPostingResult(
            success=False,
            journal_entry_id=reclass_journal.journal_entry_id,
            message=reclass_result.message,
        )

    fiscal_period = db.scalar(
        select(FiscalPeriod).where(
            and_(
                FiscalPeriod.organization_id == org_id,
                FiscalPeriod.start_date <= payment.payment_date,
                FiscalPeriod.end_date >= payment.payment_date,
            )
        )
    )
    if fiscal_period:
        for payload in tax_payloads:
            tax_transaction_service.create_payment_recognition(
                db=db,
                organization_id=org_id,
                fiscal_period_id=fiscal_period.fiscal_period_id,
                tax_code_id=payload["tax_code_id"],
                transaction_date=payment.payment_date,
                source_document_type="CUSTOMER_PAYMENT",
                source_document_id=pay_id,
                source_document_line_id=payload["source_document_line_id"],
                source_document_reference=payload["source_document_reference"],
                is_purchase=False,
                base_amount=payload["base_amount"],
                tax_amount=payload["tax_amount"],
                currency_code=payment.currency_code,
                exchange_rate=exchange_rate,
                counterparty_name=customer.legal_name,
                counterparty_tax_id=customer.tax_identification_number,
            )

    return None


def post_payment(
    db: Session,
    organization_id: UUID,
    payment_id: UUID,
    posting_date: date,
    posted_by_user_id: UUID,
    idempotency_key: str | None = None,
) -> ARPostingResult:
    """
    Post a customer payment to the general ledger.

    Creates a journal entry with:
    - Debit: Bank/Cash account
    - Credit: AR Control account

    Args:
        db: Database session
        organization_id: Organization scope
        payment_id: Payment to post
        posting_date: Date for the GL posting
        posted_by_user_id: User posting
        idempotency_key: Optional idempotency key

    Returns:
        ARPostingResult with outcome
    """
    from app.models.finance.ar.customer_payment import CustomerPayment, PaymentStatus

    org_id = coerce_uuid(organization_id)
    pay_id = coerce_uuid(payment_id)
    user_id = coerce_uuid(posted_by_user_id)

    # Load payment
    payment = db.get(CustomerPayment, pay_id)
    if not payment or payment.organization_id != org_id:
        return ARPostingResult(success=False, message="Payment not found")

    # Allow posting for APPROVED (normal workflow) and for payments that are
    # already in a posted state but missing GL entries (sync/import backfill).
    postable_statuses = {
        PaymentStatus.APPROVED,
        PaymentStatus.CLEARED,
    }
    if payment.status not in postable_statuses:
        return ARPostingResult(
            success=False,
            message=f"Payment must be APPROVED or CLEARED to post (current: {payment.status.value})",
        )

    # Skip zero-amount payments — nothing meaningful to post to GL
    if payment.amount == Decimal("0"):
        return ARPostingResult(
            success=True,
            message="Zero amount payment — no GL posting needed",
        )

    # Load customer
    customer = db.get(Customer, payment.customer_id)
    if not customer:
        return ARPostingResult(success=False, message="Customer not found")

    exchange_rate = payment.exchange_rate or Decimal("1.0")
    functional_amount = payment.amount * exchange_rate

    if not payment.bank_account_id:
        return ARPostingResult(
            success=False, message="Payment has no bank account linked"
        )

    bank_gl_account_id = _resolve_bank_gl_account_id(
        db,
        org_id,
        payment.bank_account_id,
    )
    if not bank_gl_account_id:
        return ARPostingResult(
            success=False,
            message="Payment bank account is not mapped to a valid GL account",
        )

    # Build journal lines
    journal_lines = [
        # Debit Bank/Cash
        JournalLineInput(
            account_id=bank_gl_account_id,
            debit_amount=payment.amount,
            credit_amount=Decimal("0"),
            debit_amount_functional=functional_amount,
            credit_amount_functional=Decimal("0"),
            description=f"AR Payment: {payment.reference}",
        ),
        # Credit AR Control
        JournalLineInput(
            account_id=customer.ar_control_account_id,
            debit_amount=Decimal("0"),
            credit_amount=payment.amount,
            debit_amount_functional=Decimal("0"),
            credit_amount_functional=functional_amount,
            description=f"Payment from {customer.legal_name}",
        ),
    ]

    # Create journal entry
    journal_input = JournalInput(
        journal_type=JournalType.STANDARD,
        entry_date=payment.payment_date,
        posting_date=posting_date,
        description=f"AR Payment {payment.payment_number} - {customer.legal_name}",
        reference=payment.reference,
        currency_code=payment.currency_code,
        exchange_rate=exchange_rate,
        lines=journal_lines,
        source_module="AR",
        source_document_type="CUSTOMER_PAYMENT",
        source_document_id=pay_id,
        correlation_id=payment.correlation_id,
    )

    journal, error = BasePostingAdapter.create_and_approve_journal(
        db,
        org_id,
        journal_input,
        user_id,
        error_prefix="Journal creation failed",
    )
    if error:
        return ARPostingResult(success=False, message=error.message)

    # Post to ledger
    if not idempotency_key:
        idempotency_key = BasePostingAdapter.make_idempotency_key(
            org_id, "AR:PAY", pay_id, action="post"
        )

    posting_result = BasePostingAdapter.post_to_ledger(
        db,
        organization_id=org_id,
        journal_entry_id=journal.journal_entry_id,
        posting_date=posting_date,
        idempotency_key=idempotency_key,
        source_module="AR",
        correlation_id=payment.correlation_id,
        posted_by_user_id=user_id,
        success_message="Payment posted successfully",
    )
    if not posting_result.success:
        return ARPostingResult(
            success=False,
            journal_entry_id=journal.journal_entry_id,
            message=posting_result.message,
        )

    vat_reclass_result = post_vat_reclass_for_payment(
        db,
        organization_id=org_id,
        payment=payment,
        customer=customer,
        posting_date=posting_date,
        posted_by_user_id=user_id,
    )
    if vat_reclass_result is not None and not vat_reclass_result.success:
        return vat_reclass_result

    return ARPostingResult(
        success=True,
        journal_entry_id=journal.journal_entry_id,
        posting_batch_id=posting_result.posting_batch_id,
        message=posting_result.message,
    )
