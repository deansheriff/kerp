"""
AR Posting Helpers - Shared utilities for AR GL posting.

Provides:
- Tax transaction creation for AR invoices
"""

import logging
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.finance.ar.customer import Customer
from app.models.finance.ar.invoice import Invoice
from app.models.finance.ar.invoice_line import InvoiceLine
from app.models.finance.ar.invoice_line_tax import InvoiceLineTax
from app.models.finance.ar.payment_allocation import PaymentAllocation
from app.models.finance.gl.account import Account
from app.models.finance.tax.tax_code import TaxCode, TaxType
from app.services.finance.tax.tax_transaction import tax_transaction_service

logger = logging.getLogger(__name__)


class CashVATReclassEntry(TypedDict):
    deferred_account_id: UUID
    current_account_id: UUID
    tax_amount: Decimal


class CashVATRecognitionPayload(TypedDict):
    tax_code_id: UUID
    source_document_line_id: UUID | None
    source_document_reference: str | None
    base_amount: Decimal
    tax_amount: Decimal


def _prorate(
    allocated_amount: Decimal, component_amount: Decimal, total_amount: Decimal
) -> Decimal:
    if total_amount == Decimal("0"):
        return Decimal("0")
    return ((allocated_amount * component_amount) / total_amount).quantize(
        Decimal("0.01")
    )


def resolve_tax_posting_account_id(
    db: Session,
    organization_id: UUID,
    tax_code_id: UUID,
    *,
    prefer_deferred: bool,
) -> UUID | None:
    tax_code = db.get(TaxCode, tax_code_id)
    if not tax_code or tax_code.organization_id != organization_id:
        return None

    account_id = tax_code.tax_collected_account_id
    if not account_id:
        return None

    if prefer_deferred and tax_code.tax_type in {TaxType.VAT, TaxType.GST}:
        account = db.get(Account, account_id)
        if account and account.deferral_pair_account_id:
            return account.deferral_pair_account_id
    return account_id


def create_tax_transactions(
    db: Session,
    organization_id: UUID,
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Customer,
    exchange_rate: Decimal,
    is_credit_note: bool = False,
) -> list[UUID]:
    """
    Create tax transactions for invoice lines with tax codes.

    Args:
        db: Database session
        organization_id: Organization scope
        invoice: The invoice being posted
        lines: Invoice lines
        customer: Customer for counterparty info
        exchange_rate: Exchange rate to functional currency
        is_credit_note: Whether this is a credit note (negative amounts)

    Returns:
        List of created tax transaction IDs
    """
    from app.models.finance.gl.fiscal_period import FiscalPeriod

    tax_transaction_ids: list[UUID] = []

    # Get fiscal period from invoice date
    fiscal_period = db.scalars(
        select(FiscalPeriod).where(
            and_(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= invoice.invoice_date,
                FiscalPeriod.end_date >= invoice.invoice_date,
            )
        )
    ).first()

    if not fiscal_period:
        # No fiscal period found - skip tax transactions
        return tax_transaction_ids

    for line in lines:
        if not line.tax_code_id or line.tax_amount == Decimal("0"):
            continue

        # For credit notes, we record negative tax (reduces output tax)
        base_amount = line.line_amount if not is_credit_note else -line.line_amount

        try:
            tax_txn = tax_transaction_service.create_from_invoice_line(
                db=db,
                organization_id=organization_id,
                fiscal_period_id=fiscal_period.fiscal_period_id,
                tax_code_id=line.tax_code_id,
                invoice_id=invoice.invoice_id,
                invoice_line_id=line.line_id,
                invoice_number=invoice.invoice_number,
                transaction_date=invoice.invoice_date,
                is_purchase=False,  # AR = OUTPUT tax (sales)
                base_amount=base_amount,
                currency_code=invoice.currency_code,
                counterparty_name=customer.legal_name,
                counterparty_tax_id=customer.tax_identification_number,
                exchange_rate=exchange_rate,
            )
            tax_transaction_ids.append(tax_txn.transaction_id)
        except Exception:
            # Log error but don't fail the posting
            logger.exception(
                "create_tax_transaction failed for AR invoice %s",
                invoice.invoice_number,
            )

    # Auto-refresh tax return for this period
    if tax_transaction_ids and fiscal_period:
        try:
            from app.models.finance.tax.tax_transaction import TaxTransaction as TaxTxn
            from app.services.finance.tax.tax_return import TaxReturnService

            first_txn = db.get(TaxTxn, tax_transaction_ids[0])
            if first_txn:
                TaxReturnService.auto_refresh_return(
                    db,
                    organization_id,
                    fiscal_period.fiscal_period_id,
                    first_txn.jurisdiction_id,
                    organization_id,  # system user fallback
                )
        except Exception:
            logger.exception(
                "Failed to auto-refresh tax return for AR invoice %s (non-blocking)",
                invoice.invoice_number,
            )

    return tax_transaction_ids


def build_cash_vat_reclass_entries(
    db: Session,
    organization_id: UUID,
    allocations: list[PaymentAllocation],
) -> tuple[list[CashVATReclassEntry], list[CashVATRecognitionPayload]]:
    """Build AR payment-time VAT reclass entries and tax-recognition payloads."""
    journal_entries: list[CashVATReclassEntry] = []
    tax_payloads: list[CashVATRecognitionPayload] = []

    for allocation in allocations:
        invoice = db.get(Invoice, allocation.invoice_id)
        if not invoice or invoice.organization_id != organization_id:
            continue
        if invoice.total_amount == Decimal("0"):
            continue

        line_taxes = db.scalars(
            select(InvoiceLineTax)
            .join(InvoiceLine, InvoiceLine.line_id == InvoiceLineTax.line_id)
            .join(TaxCode, TaxCode.tax_code_id == InvoiceLineTax.tax_code_id)
            .where(
                InvoiceLine.invoice_id == invoice.invoice_id,
                TaxCode.tax_type.in_({TaxType.VAT, TaxType.GST}),
            )
        ).all()

        for line_tax in line_taxes:
            current_account_id = resolve_tax_posting_account_id(
                db,
                organization_id,
                line_tax.tax_code_id,
                prefer_deferred=False,
            )
            deferred_account_id = resolve_tax_posting_account_id(
                db,
                organization_id,
                line_tax.tax_code_id,
                prefer_deferred=True,
            )
            if (
                not current_account_id
                or not deferred_account_id
                or current_account_id == deferred_account_id
            ):
                continue

            tax_amount = _prorate(
                allocation.allocated_amount,
                line_tax.tax_amount,
                invoice.total_amount,
            )
            base_amount = _prorate(
                allocation.allocated_amount,
                line_tax.base_amount,
                invoice.total_amount,
            )
            if tax_amount == Decimal("0"):
                continue

            journal_entries.append(
                {
                    "deferred_account_id": deferred_account_id,
                    "current_account_id": current_account_id,
                    "tax_amount": tax_amount,
                }
            )
            tax_payloads.append(
                {
                    "tax_code_id": line_tax.tax_code_id,
                    "source_document_line_id": allocation.allocation_id,
                    "source_document_reference": invoice.invoice_number,
                    "base_amount": base_amount,
                    "tax_amount": tax_amount,
                }
            )

    return journal_entries, tax_payloads
