#!/usr/bin/env python3
"""
Backfill deferred VAT journals and cash-basis tax recognition.

This script replays the deferred-VAT architecture onto historical data:

1. AR invoices:
   DR current VAT payable / CR deferred output VAT, dated invoice_date.
2. AP invoices:
   DR deferred input VAT / CR original invoice debit account, dated invoice_date.
3. AR customer payments:
   create VAT reclass journal and cash-basis tax rows, dated payment_date.
4. AP supplier payments:
   create VAT reclass journal and cash-basis tax rows, dated payment_date.

Idempotency:
- Invoice backfill journals are keyed by source_document_type + source_document_id.
- Payment replay reuses the posting helpers, which skip when the VAT reclass
  journal already exists.

Usage:
    poetry run python scripts/migration/2026-04-30_backfill_deferred_vat.py --dry-run
    poetry run python scripts/migration/2026-04-30_backfill_deferred_vat.py --apply
"""

from __future__ import annotations

import argparse
from collections import Counter
import logging
import sys
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

sys.path.insert(0, ".")

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.finance.core_org.organization import Organization
from app.models.finance.ap.supplier import Supplier
from app.models.finance.ap.supplier_invoice import SupplierInvoice
from app.models.finance.ap.supplier_invoice_line import SupplierInvoiceLine
from app.models.finance.ap.supplier_invoice_line_tax import SupplierInvoiceLineTax
from app.models.finance.ap.supplier_payment import APPaymentStatus, SupplierPayment
from app.models.finance.ar.customer import Customer
from app.models.finance.ar.customer_payment import CustomerPayment, PaymentStatus
from app.models.finance.ar.invoice import Invoice
from app.models.finance.ar.invoice_line import InvoiceLine
from app.models.finance.ar.invoice_line_tax import InvoiceLineTax
from app.models.finance.gl.account import Account
from app.models.finance.gl.journal_entry import JournalEntry, JournalStatus, JournalType
from app.models.finance.tax.tax_code import TaxCode, TaxType
from app.services.common import coerce_uuid
from app.services.finance.ap.posting.helpers import determine_debit_account
from app.services.finance.ap.posting.payment import (
    post_vat_reclass_for_payment as post_ap_vat_reclass_for_payment,
)
from app.services.finance.ar.posting.payment import (
    post_vat_reclass_for_payment as post_ar_vat_reclass_for_payment,
)
from app.services.finance.gl.journal import JournalInput, JournalLineInput
from app.services.finance.posting.base import BasePostingAdapter


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_deferred_vat")

PHASE_AR_INVOICES = "ar-invoices"
PHASE_AP_INVOICES = "ap-invoices"
PHASE_AR_PAYMENTS = "ar-payments"
PHASE_AP_PAYMENTS = "ap-payments"
ALL_PHASES = (
    PHASE_AR_INVOICES,
    PHASE_AP_INVOICES,
    PHASE_AR_PAYMENTS,
    PHASE_AP_PAYMENTS,
)


@dataclass
class BackfillStats:
    ar_invoice_candidates: int = 0
    ar_invoice_posted: int = 0
    ar_invoice_skipped: int = 0
    ap_invoice_candidates: int = 0
    ap_invoice_posted: int = 0
    ap_invoice_skipped: int = 0
    ar_payment_candidates: int = 0
    ar_payment_replayed: int = 0
    ar_payment_skipped: int = 0
    ap_payment_candidates: int = 0
    ap_payment_replayed: int = 0
    ap_payment_skipped: int = 0
    failures: int = 0
    ap_invoice_skip_reason_counts: Counter[str] = field(default_factory=Counter)

    def add(self, other: BackfillStats) -> None:
        self.ar_invoice_candidates += other.ar_invoice_candidates
        self.ar_invoice_posted += other.ar_invoice_posted
        self.ar_invoice_skipped += other.ar_invoice_skipped
        self.ap_invoice_candidates += other.ap_invoice_candidates
        self.ap_invoice_posted += other.ap_invoice_posted
        self.ap_invoice_skipped += other.ap_invoice_skipped
        self.ar_payment_candidates += other.ar_payment_candidates
        self.ar_payment_replayed += other.ar_payment_replayed
        self.ar_payment_skipped += other.ar_payment_skipped
        self.ap_payment_candidates += other.ap_payment_candidates
        self.ap_payment_replayed += other.ap_payment_replayed
        self.ap_payment_skipped += other.ap_payment_skipped
        self.failures += other.failures
        self.ap_invoice_skip_reason_counts.update(other.ap_invoice_skip_reason_counts)


@dataclass(frozen=True)
class BackfillRunOptions:
    phases: tuple[str, ...]
    limit: int | None
    offset: int
    from_date: date | None
    to_date: date | None
    batch_size: int | None = None
    max_batches: int | None = None
    report_ap_invoice_skips: bool = False


def _parse_iso_date(raw: str) -> date:
    return date.fromisoformat(raw)


def _is_zero_stats(stats: BackfillStats) -> bool:
    return (
        stats.ar_invoice_candidates == 0
        and stats.ar_invoice_posted == 0
        and stats.ar_invoice_skipped == 0
        and stats.ap_invoice_candidates == 0
        and stats.ap_invoice_posted == 0
        and stats.ap_invoice_skipped == 0
        and stats.ar_payment_candidates == 0
        and stats.ar_payment_replayed == 0
        and stats.ar_payment_skipped == 0
        and stats.ap_payment_candidates == 0
        and stats.ap_payment_replayed == 0
        and stats.ap_payment_skipped == 0
        and stats.failures == 0
    )


def _log_summary(stats: BackfillStats, *, label: str, apply: bool) -> None:
    logger.info("=" * 72)
    logger.info(
        "Deferred VAT backfill summary [%s] %s", "APPLY" if apply else "DRY RUN", label
    )
    logger.info(
        "AR invoices:   candidates=%d posted=%d skipped=%d",
        stats.ar_invoice_candidates,
        stats.ar_invoice_posted,
        stats.ar_invoice_skipped,
    )
    logger.info(
        "AP invoices:   candidates=%d posted=%d skipped=%d",
        stats.ap_invoice_candidates,
        stats.ap_invoice_posted,
        stats.ap_invoice_skipped,
    )
    if stats.ap_invoice_skip_reason_counts:
        logger.info(
            "AP invoice skip reasons: %s",
            ", ".join(
                f"{reason}={count}"
                for reason, count in sorted(stats.ap_invoice_skip_reason_counts.items())
            ),
        )
    logger.info(
        "AR payments:   candidates=%d replayed=%d skipped=%d",
        stats.ar_payment_candidates,
        stats.ar_payment_replayed,
        stats.ar_payment_skipped,
    )
    logger.info(
        "AP payments:   candidates=%d replayed=%d skipped=%d",
        stats.ap_payment_candidates,
        stats.ap_payment_replayed,
        stats.ap_payment_skipped,
    )
    logger.info("Failures: %d", stats.failures)
    logger.info("=" * 72)


def _log_dry_run_detail(verbose: bool, message: str, *args: object) -> None:
    if verbose:
        logger.info(message, *args)


def _record_ap_invoice_skip(
    stats: BackfillStats,
    *,
    invoice_number: str,
    reasons: set[str],
    report_details: bool,
) -> None:
    normalized_reasons = reasons or {"unknown"}
    stats.ap_invoice_skipped += 1
    stats.ap_invoice_skip_reason_counts.update(normalized_reasons)
    if report_details:
        logger.info(
            "AP invoice skip %s: %s",
            invoice_number,
            ", ".join(sorted(normalized_reasons)),
        )


def _apply_window(
    stmt: Select,
    *,
    dated_column,
    options: BackfillRunOptions,
) -> Select:
    if options.from_date is not None:
        stmt = stmt.where(dated_column >= options.from_date)
    if options.to_date is not None:
        stmt = stmt.where(dated_column <= options.to_date)
    if options.offset:
        stmt = stmt.offset(options.offset)
    if options.limit is not None:
        stmt = stmt.limit(options.limit)
    return stmt


def _get_org_id(db: Session, org_id_arg: str | None) -> UUID:
    if org_id_arg:
        return coerce_uuid(org_id_arg)

    org = db.scalar(select(Organization))
    if not org:
        raise RuntimeError("No organization found")
    return org.organization_id


def _journal_exists(
    db: Session,
    *,
    organization_id: UUID,
    source_module: str,
    source_document_type: str,
    source_document_id: UUID,
) -> bool:
    existing = db.scalar(
        select(JournalEntry).where(
            JournalEntry.organization_id == organization_id,
            JournalEntry.source_module == source_module,
            JournalEntry.source_document_type == source_document_type,
            JournalEntry.source_document_id == source_document_id,
            JournalEntry.status.notin_([JournalStatus.VOID, JournalStatus.REVERSED]),
        )
    )
    return existing is not None


def _post_reclass_journal(
    db: Session,
    *,
    organization_id: UUID,
    source_module: str,
    source_document_type: str,
    source_document_id: UUID,
    entry_date: date,
    description: str,
    reference: str,
    lines: list[JournalLineInput],
    correlation_id: str | None,
    user_id: UUID,
) -> bool:
    journal_input = JournalInput(
        journal_type=JournalType.ADJUSTMENT,
        entry_date=entry_date,
        posting_date=entry_date,
        description=description,
        reference=reference,
        currency_code="NGN",
        exchange_rate=Decimal("1.0"),
        lines=lines,
        source_module=source_module,
        source_document_type=source_document_type,
        source_document_id=source_document_id,
        correlation_id=correlation_id,
    )
    journal, error = BasePostingAdapter.create_and_approve_journal(
        db,
        organization_id,
        journal_input,
        user_id,
        error_prefix="Deferred VAT journal creation failed",
    )
    if error:
        raise RuntimeError(error.message)

    result = BasePostingAdapter.post_to_ledger(
        db,
        organization_id=organization_id,
        journal_entry_id=journal.journal_entry_id,
        posting_date=entry_date,
        idempotency_key=BasePostingAdapter.make_idempotency_key(
            organization_id,
            f"{source_module}:{source_document_type}",
            source_document_id,
            action="post",
        ),
        source_module=source_module,
        correlation_id=correlation_id,
        posted_by_user_id=user_id,
        success_message="Deferred VAT journal posted successfully",
    )
    if not result.success:
        raise RuntimeError(result.message)
    return True


def _backfill_ar_invoices(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    apply: bool,
    stats: BackfillStats,
    verbose: bool,
    options: BackfillRunOptions,
) -> None:
    stmt = (
        select(Invoice)
        .where(
            Invoice.organization_id == organization_id,
            Invoice.journal_entry_id.is_not(None),
        )
        .order_by(Invoice.invoice_date, Invoice.invoice_number)
    )
    invoices = list(
        db.scalars(
            _apply_window(
                stmt,
                dated_column=Invoice.invoice_date,
                options=options,
            )
        ).all()
    )

    for invoice in invoices:
        line_taxes = list(
            db.scalars(
                select(InvoiceLineTax)
                .join(InvoiceLine, InvoiceLine.line_id == InvoiceLineTax.line_id)
                .join(TaxCode, TaxCode.tax_code_id == InvoiceLineTax.tax_code_id)
                .where(
                    InvoiceLine.invoice_id == invoice.invoice_id,
                    TaxCode.tax_type.in_({TaxType.VAT, TaxType.GST}),
                )
            ).all()
        )
        if not line_taxes:
            continue

        stats.ar_invoice_candidates += 1
        if _journal_exists(
            db,
            organization_id=organization_id,
            source_module="AR",
            source_document_type="AR_INVOICE_VAT_DEFERRAL",
            source_document_id=invoice.invoice_id,
        ):
            stats.ar_invoice_skipped += 1
            continue

        grouped: dict[tuple[UUID, UUID], Decimal] = {}
        for line_tax in line_taxes:
            tax_code = db.get(TaxCode, line_tax.tax_code_id)
            if not tax_code or not tax_code.tax_collected_account_id:
                continue
            current_account = db.get(Account, tax_code.tax_collected_account_id)
            if not current_account or not current_account.deferral_pair_account_id:
                continue
            key = (
                tax_code.tax_collected_account_id,
                current_account.deferral_pair_account_id,
            )
            grouped[key] = grouped.get(key, Decimal("0")) + line_tax.tax_amount

        if not grouped:
            stats.ar_invoice_skipped += 1
            continue

        if not apply:
            _log_dry_run_detail(
                verbose,
                "DRY RUN AR invoice %s: would defer %s VAT bucket(s)",
                invoice.invoice_number,
                len(grouped),
            )
            continue

        lines: list[JournalLineInput] = []
        for (current_account_id, deferred_account_id), amount in grouped.items():
            lines.append(
                JournalLineInput(
                    account_id=current_account_id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    description=f"Backfill deferred VAT for invoice {invoice.invoice_number}",
                )
            )
            lines.append(
                JournalLineInput(
                    account_id=deferred_account_id,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                    description=f"Backfill deferred VAT for invoice {invoice.invoice_number}",
                )
            )

        _post_reclass_journal(
            db,
            organization_id=organization_id,
            source_module="AR",
            source_document_type="AR_INVOICE_VAT_DEFERRAL",
            source_document_id=invoice.invoice_id,
            entry_date=invoice.invoice_date,
            description=f"Backfill deferred VAT for AR invoice {invoice.invoice_number}",
            reference=f"AR-VAT-DEF-{invoice.invoice_number}",
            lines=lines,
            correlation_id=invoice.correlation_id,
            user_id=user_id,
        )
        stats.ar_invoice_posted += 1
        db.commit()


def _backfill_ap_invoices(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    apply: bool,
    stats: BackfillStats,
    verbose: bool,
    options: BackfillRunOptions,
) -> None:
    stmt = (
        select(SupplierInvoice)
        .where(
            SupplierInvoice.organization_id == organization_id,
            SupplierInvoice.journal_entry_id.is_not(None),
        )
        .order_by(SupplierInvoice.invoice_date, SupplierInvoice.invoice_number)
    )
    invoices = list(
        db.scalars(
            _apply_window(
                stmt,
                dated_column=SupplierInvoice.invoice_date,
                options=options,
            )
        ).all()
    )

    for invoice in invoices:
        supplier = db.get(Supplier, invoice.supplier_id)
        if not supplier:
            continue

        line_taxes = list(
            db.scalars(
                select(SupplierInvoiceLineTax)
                .join(
                    SupplierInvoiceLine,
                    SupplierInvoiceLine.line_id == SupplierInvoiceLineTax.line_id,
                )
                .join(
                    TaxCode, TaxCode.tax_code_id == SupplierInvoiceLineTax.tax_code_id
                )
                .where(
                    SupplierInvoiceLine.invoice_id == invoice.invoice_id,
                    TaxCode.tax_type.in_({TaxType.VAT, TaxType.GST}),
                    TaxCode.is_recoverable.is_(True),
                )
            ).all()
        )
        if not line_taxes:
            continue

        stats.ap_invoice_candidates += 1
        if _journal_exists(
            db,
            organization_id=organization_id,
            source_module="AP",
            source_document_type="SUPPLIER_INVOICE_VAT_DEFERRAL",
            source_document_id=invoice.invoice_id,
        ):
            _record_ap_invoice_skip(
                stats,
                invoice_number=invoice.invoice_number,
                reasons={"existing_reclass_journal"},
                report_details=options.report_ap_invoice_skips,
            )
            continue

        grouped: dict[tuple[UUID, UUID], Decimal] = {}
        skip_reasons: set[str] = set()
        for line_tax in line_taxes:
            line = db.get(SupplierInvoiceLine, line_tax.line_id)
            if not line:
                skip_reasons.add("missing_invoice_line")
                continue
            tax_code = db.get(TaxCode, line_tax.tax_code_id)
            if not tax_code:
                skip_reasons.add("missing_tax_code")
                continue
            if not tax_code.tax_paid_account_id:
                skip_reasons.add("missing_tax_paid_account")
                continue
            current_account = db.get(Account, tax_code.tax_paid_account_id)
            if not current_account:
                skip_reasons.add("missing_current_tax_account")
                continue
            if not current_account.deferral_pair_account_id:
                skip_reasons.add("missing_deferral_pair_account")
                continue

            source_debit_account_id = determine_debit_account(
                db, organization_id, line, supplier
            )
            if not source_debit_account_id:
                skip_reasons.add("missing_source_debit_account")
                continue

            key = (
                current_account.deferral_pair_account_id,
                source_debit_account_id,
            )
            grouped[key] = grouped.get(key, Decimal("0")) + line_tax.tax_amount

        if not grouped:
            _record_ap_invoice_skip(
                stats,
                invoice_number=invoice.invoice_number,
                reasons=skip_reasons or {"no_grouped_vat_entries"},
                report_details=options.report_ap_invoice_skips,
            )
            continue

        if not apply:
            _log_dry_run_detail(
                verbose,
                "DRY RUN AP invoice %s: would defer %s VAT bucket(s)",
                invoice.invoice_number,
                len(grouped),
            )
            continue

        lines: list[JournalLineInput] = []
        for (deferred_account_id, source_debit_account_id), amount in grouped.items():
            lines.append(
                JournalLineInput(
                    account_id=deferred_account_id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    description=f"Backfill deferred VAT for supplier invoice {invoice.invoice_number}",
                )
            )
            lines.append(
                JournalLineInput(
                    account_id=source_debit_account_id,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                    description=f"Backfill deferred VAT for supplier invoice {invoice.invoice_number}",
                )
            )

        _post_reclass_journal(
            db,
            organization_id=organization_id,
            source_module="AP",
            source_document_type="SUPPLIER_INVOICE_VAT_DEFERRAL",
            source_document_id=invoice.invoice_id,
            entry_date=invoice.invoice_date,
            description=f"Backfill deferred VAT for supplier invoice {invoice.invoice_number}",
            reference=f"AP-VAT-DEF-{invoice.invoice_number}",
            lines=lines,
            correlation_id=invoice.invoice_number,
            user_id=user_id,
        )
        stats.ap_invoice_posted += 1
        db.commit()


def _backfill_ar_payments(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    apply: bool,
    stats: BackfillStats,
    verbose: bool,
    options: BackfillRunOptions,
) -> None:
    stmt = (
        select(CustomerPayment)
        .where(
            CustomerPayment.organization_id == organization_id,
            CustomerPayment.status == PaymentStatus.CLEARED,
        )
        .order_by(CustomerPayment.payment_date, CustomerPayment.payment_number)
    )
    payments = list(
        db.scalars(
            _apply_window(
                stmt,
                dated_column=CustomerPayment.payment_date,
                options=options,
            )
        ).all()
    )

    for payment in payments:
        customer = db.get(Customer, payment.customer_id)
        if not customer:
            continue
        stats.ar_payment_candidates += 1

        if _journal_exists(
            db,
            organization_id=organization_id,
            source_module="AR",
            source_document_type="CUSTOMER_PAYMENT_VAT_RECLASS",
            source_document_id=payment.payment_id,
        ):
            stats.ar_payment_skipped += 1
            continue

        if not apply:
            _log_dry_run_detail(
                verbose,
                "DRY RUN AR payment %s: would replay VAT reclass",
                payment.payment_number,
            )
            continue

        result = post_ar_vat_reclass_for_payment(
            db,
            organization_id=organization_id,
            payment=payment,
            customer=customer,
            posting_date=payment.payment_date,
            posted_by_user_id=user_id,
        )
        if result is not None and not result.success:
            raise RuntimeError(result.message)
        if result is None:
            stats.ar_payment_skipped += 1
            continue
        stats.ar_payment_replayed += 1
        db.commit()


def _backfill_ap_payments(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    apply: bool,
    stats: BackfillStats,
    verbose: bool,
    options: BackfillRunOptions,
) -> None:
    stmt = (
        select(SupplierPayment)
        .where(
            SupplierPayment.organization_id == organization_id,
            SupplierPayment.status.in_({APPaymentStatus.SENT, APPaymentStatus.CLEARED}),
        )
        .order_by(SupplierPayment.payment_date, SupplierPayment.payment_number)
    )
    payments = list(
        db.scalars(
            _apply_window(
                stmt,
                dated_column=SupplierPayment.payment_date,
                options=options,
            )
        ).all()
    )

    for payment in payments:
        supplier = db.get(Supplier, payment.supplier_id)
        if not supplier:
            continue
        stats.ap_payment_candidates += 1

        if _journal_exists(
            db,
            organization_id=organization_id,
            source_module="AP",
            source_document_type="SUPPLIER_PAYMENT_VAT_RECLASS",
            source_document_id=payment.payment_id,
        ):
            stats.ap_payment_skipped += 1
            continue

        if not apply:
            _log_dry_run_detail(
                verbose,
                "DRY RUN AP payment %s: would replay VAT reclass",
                payment.payment_number,
            )
            continue

        result = post_ap_vat_reclass_for_payment(
            db,
            organization_id=organization_id,
            payment=payment,
            supplier=supplier,
            posting_date=payment.payment_date,
            posted_by_user_id=user_id,
        )
        if result is not None and not result.success:
            raise RuntimeError(result.message)
        if result is None:
            stats.ap_payment_skipped += 1
            continue
        stats.ap_payment_replayed += 1
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill deferred VAT journals.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview only")
    mode.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--org-id", help="Organization UUID (defaults to first org)")
    parser.add_argument(
        "--user-id",
        help="User UUID to attribute postings to (defaults to org_id/system user)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each candidate during dry-run instead of summary only",
    )
    parser.add_argument(
        "--phase",
        action="append",
        choices=ALL_PHASES,
        help="Run only the selected phase(s); may be provided multiple times",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit rows scanned in each selected phase after date filtering",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset rows scanned in each selected phase after date filtering",
    )
    parser.add_argument(
        "--from-date",
        type=_parse_iso_date,
        help="Inclusive lower date bound in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--to-date",
        type=_parse_iso_date,
        help="Inclusive upper date bound in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Automatically iterate offsets in batches of this size",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        help="Stop auto-batching after this many batches",
    )
    parser.add_argument(
        "--report-ap-invoice-skips",
        action="store_true",
        help="Log AP invoice skip details and include skip-reason counts in summaries",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be a positive integer")
    if args.batch_size is not None and args.batch_size <= 0:
        raise SystemExit("--batch-size must be a positive integer")
    if args.max_batches is not None and args.max_batches <= 0:
        raise SystemExit("--max-batches must be a positive integer")
    if args.offset < 0:
        raise SystemExit("--offset must be zero or greater")
    if args.from_date and args.to_date and args.from_date > args.to_date:
        raise SystemExit("--from-date cannot be later than --to-date")
    if args.batch_size is not None and args.limit is not None:
        raise SystemExit("--batch-size cannot be combined with --limit")
    if args.batch_size is None and args.max_batches is not None:
        raise SystemExit("--max-batches requires --batch-size")

    with SessionLocal() as db:
        org_id = _get_org_id(db, args.org_id)
        user_id = coerce_uuid(args.user_id) if args.user_id else org_id
        apply = bool(args.apply)
        verbose = bool(args.verbose)
        options = BackfillRunOptions(
            phases=tuple(args.phase or ALL_PHASES),
            limit=args.limit,
            offset=args.offset,
            from_date=args.from_date,
            to_date=args.to_date,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            report_ap_invoice_skips=bool(args.report_ap_invoice_skips),
        )

        phase_handlers = {
            PHASE_AR_INVOICES: _backfill_ar_invoices,
            PHASE_AP_INVOICES: _backfill_ap_invoices,
            PHASE_AR_PAYMENTS: _backfill_ar_payments,
            PHASE_AP_PAYMENTS: _backfill_ap_payments,
        }
        total_stats = BackfillStats()

        if options.batch_size is None:
            run_batches = (options,)
        else:
            run_batches = []
            batch_count = options.max_batches or 10**9
            for batch_index in range(batch_count):
                run_batches.append(
                    replace(
                        options,
                        limit=options.batch_size,
                        offset=options.offset + (batch_index * options.batch_size),
                    )
                )

        for batch_index, batch_options in enumerate(run_batches, start=1):
            logger.info(
                "Run scope: phases=%s limit=%s offset=%s from_date=%s to_date=%s mode=%s batch=%s",
                ",".join(batch_options.phases),
                batch_options.limit if batch_options.limit is not None else "ALL",
                batch_options.offset,
                batch_options.from_date.isoformat()
                if batch_options.from_date
                else "NONE",
                batch_options.to_date.isoformat() if batch_options.to_date else "NONE",
                "APPLY" if apply else "DRY RUN",
                batch_index if options.batch_size is not None else "SINGLE",
            )
            batch_stats = BackfillStats()

            for phase_name in batch_options.phases:
                phase = phase_handlers[phase_name]
                try:
                    phase(
                        db,
                        organization_id=org_id,
                        user_id=user_id,
                        apply=apply,
                        stats=batch_stats,
                        verbose=verbose,
                        options=batch_options,
                    )
                except Exception:
                    batch_stats.failures += 1
                    db.rollback()
                    logger.exception("Phase %s failed", phase_name)

            if options.batch_size is not None:
                _log_summary(
                    batch_stats,
                    label=f"[batch {batch_index} offset={batch_options.offset}]",
                    apply=apply,
                )

            total_stats.add(batch_stats)

            if options.batch_size is None:
                continue
            if _is_zero_stats(batch_stats):
                logger.info(
                    "Stopping auto-batch after batch %s because no rows were processed in scope.",
                    batch_index,
                )
                break

        _log_summary(total_stats, label="[total]", apply=apply)


if __name__ == "__main__":
    main()
