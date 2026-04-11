from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.models.finance.ar.customer_payment import (
    CustomerPayment,
    PaymentStatus,
)
from app.models.finance.ar.invoice import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
)
from app.models.finance.ar.payment_allocation import (
    PaymentAllocation,
)

logger = logging.getLogger(__name__)


class AllocationMixin:
    """Payment allocation, ledger resolution, and repair logic."""

    # Provided by other mixins at runtime
    db: Any
    organization_id: UUID
    client: Any
    _customer_cache: dict[int, UUID]

    # Methods from other mixins
    _parse_date: Any

    def auto_allocate_unapplied_payments(
        self,
    ) -> dict[str, Any]:
        """Auto-allocate unapplied Splynx payments to open invoices.

        Two-tier policy:
        - Tier A (strict): exact amount match against invoice balance
        - Tier B (credit-note-aware): balance minus unapplied credits
        """
        open_statuses = {
            InvoiceStatus.POSTED,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        }

        unapplied_payments = list(
            self.db.scalars(
                select(CustomerPayment).where(
                    CustomerPayment.organization_id == self.organization_id,
                    CustomerPayment.splynx_id.isnot(None),
                    CustomerPayment.status == PaymentStatus.CLEARED,
                    ~select(PaymentAllocation.allocation_id)
                    .where(PaymentAllocation.payment_id == CustomerPayment.payment_id)
                    .exists(),
                )
            ).all()
        )
        if not unapplied_payments:
            return {
                "allocated": 0,
                "ambiguous": 0,
                "no_candidate": 0,
                "errors": [],
            }

        open_invoices = list(
            self.db.scalars(
                select(Invoice).where(
                    Invoice.organization_id == self.organization_id,
                    Invoice.invoice_type == InvoiceType.STANDARD,
                    Invoice.status.in_(open_statuses),
                )
            ).all()
        )

        credit_notes = list(
            self.db.scalars(
                select(Invoice).where(
                    Invoice.organization_id == self.organization_id,
                    Invoice.invoice_type == InvoiceType.CREDIT_NOTE,
                    Invoice.status == InvoiceStatus.POSTED,
                )
            ).all()
        )
        customer_credit: dict[UUID, Decimal] = {}
        for cn in credit_notes:
            available = cn.total_amount - cn.amount_paid
            if available > Decimal("0"):
                customer_credit[cn.customer_id] = (
                    customer_credit.get(cn.customer_id, Decimal("0")) + available
                )

        def _to_cents(value: Decimal) -> int:
            return int(value.quantize(Decimal("0.01")) * 100)

        gross_index: dict[tuple[UUID, int], list[Invoice]] = {}
        net_index: dict[tuple[UUID, int], list[Invoice]] = {}
        for inv in open_invoices:
            balance_due = getattr(
                inv,
                "balance_due",
                inv.total_amount - inv.amount_paid,
            )
            if balance_due <= Decimal("0"):
                continue
            key = (inv.customer_id, _to_cents(balance_due))
            gross_index.setdefault(key, []).append(inv)

            credit = customer_credit.get(inv.customer_id, Decimal("0"))
            if credit > Decimal("0"):
                net_balance = balance_due - credit
                if net_balance > Decimal("0"):
                    net_key = (
                        inv.customer_id,
                        _to_cents(net_balance),
                    )
                    net_index.setdefault(net_key, []).append(inv)

        allocated = 0
        ambiguous = 0
        no_candidate = 0
        errors: list[str] = []
        used_invoice_ids: set[UUID] = set()
        used_payment_ids: set[UUID] = set()

        sorted_payments = sorted(
            unapplied_payments,
            key=lambda p: (
                p.customer_id,
                p.payment_date,
                str(p.payment_id),
            ),
        )
        for payment in sorted_payments:
            try:
                pmt_key = (
                    payment.customer_id,
                    _to_cents(payment.amount),
                )

                candidates = [
                    inv
                    for inv in gross_index.get(pmt_key, [])
                    if inv.invoice_id not in used_invoice_ids
                ]

                tier_b = False
                if not candidates:
                    candidates = [
                        inv
                        for inv in net_index.get(pmt_key, [])
                        if inv.invoice_id not in used_invoice_ids
                    ]
                    tier_b = bool(candidates)

                if len(candidates) != 1:
                    if len(candidates) > 1:
                        ambiguous += 1
                    else:
                        no_candidate += 1
                    continue

                invoice = candidates[0]
                allocation = PaymentAllocation(
                    payment_id=payment.payment_id,
                    invoice_id=invoice.invoice_id,
                    allocated_amount=payment.amount,
                    allocation_date=payment.payment_date,
                )
                self.db.add(allocation)

                invoice.amount_paid = min(
                    invoice.total_amount,
                    invoice.amount_paid + payment.amount,
                )
                if invoice.amount_paid >= invoice.total_amount:
                    invoice.status = InvoiceStatus.PAID
                elif invoice.amount_paid > Decimal("0"):
                    invoice.status = InvoiceStatus.PARTIALLY_PAID
                else:
                    invoice.status = InvoiceStatus.POSTED

                used_invoice_ids.add(invoice.invoice_id)
                used_payment_ids.add(payment.payment_id)
                allocated += 1

                if tier_b:
                    logger.info(
                        "Tier-B allocation: payment %s -> "
                        "invoice %s (credit note offset "
                        "for customer %s)",
                        payment.payment_id,
                        invoice.invoice_number,
                        payment.customer_id,
                    )
            except Exception as exc:
                logger.exception(
                    "Auto-allocation error for payment %s: %s",
                    payment.payment_id,
                    exc,
                )
                errors.append(f"Payment {payment.payment_id}: {exc}")

        self.db.flush()

        still_unapplied = len(sorted_payments) - len(used_payment_ids)
        if still_unapplied:
            logger.warning(
                "%d payments remain unapplied after "
                "allocation -- these likely have "
                "invoice_id=0 in Splynx (account-level "
                "payments without a specific invoice link). "
                "Consider syncing Splynx "
                "/finance/transactions for full ledger "
                "resolution.",
                still_unapplied,
            )

        logger.info(
            "Auto-allocation complete: %d allocated, %d ambiguous, %d no-candidate",
            allocated,
            ambiguous,
            no_candidate,
        )
        return {
            "allocated": allocated,
            "ambiguous": ambiguous,
            "no_candidate": no_candidate,
            "errors": errors,
        }

    def resolve_payment_invoices_from_ledger(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Resolve unapplied payment->invoice links from ledger."""
        results: dict[str, Any] = {
            "resolved": 0,
            "already_allocated": 0,
            "invoice_not_found": 0,
            "no_ledger_link": 0,
            "errors": [],
        }

        unapplied = list(
            self.db.scalars(
                select(CustomerPayment).where(
                    CustomerPayment.organization_id == self.organization_id,
                    CustomerPayment.splynx_id.isnot(None),
                    CustomerPayment.status == PaymentStatus.CLEARED,
                    ~select(PaymentAllocation.allocation_id)
                    .where(PaymentAllocation.payment_id == CustomerPayment.payment_id)
                    .exists(),
                )
            ).all()
        )
        if not unapplied:
            logger.info("No unapplied Splynx payments to resolve")
            return results

        splynx_id_to_payment: dict[int, CustomerPayment] = {}
        for pmt in unapplied:
            if not pmt.splynx_id:
                continue
            try:
                splynx_id_to_payment[int(pmt.splynx_id)] = pmt
            except (ValueError, TypeError):
                continue

        logger.info(
            "Resolving %d unapplied Splynx payments via transaction ledger",
            len(splynx_id_to_payment),
        )

        try:
            transactions = list(
                self.client.get_transactions(
                    date_from=date_from,
                    date_to=date_to,
                )
            )
        except Exception:
            logger.exception("Failed to fetch Splynx transaction ledger")
            results["errors"].append("Failed to fetch transaction ledger")
            return results

        for txn in transactions:
            if txn.type != "payment":
                continue
            if txn.document_id not in splynx_id_to_payment:
                continue
            if not txn.invoice_id:
                results["no_ledger_link"] += 1
                continue

            payment = splynx_id_to_payment.pop(txn.document_id)

            correlation_id = f"splynx-inv-{txn.invoice_id}"
            invoice = self.db.scalar(
                select(Invoice).where(
                    Invoice.organization_id == self.organization_id,
                    Invoice.correlation_id == correlation_id,
                )
            )
            if not invoice:
                results["invoice_not_found"] += 1
                logger.debug(
                    "Ledger links payment %d to invoice %d but invoice not synced yet",
                    txn.document_id,
                    txn.invoice_id,
                )
                continue

            existing = self.db.scalar(
                select(PaymentAllocation.allocation_id).where(
                    PaymentAllocation.payment_id == payment.payment_id,
                )
            )
            if existing:
                results["already_allocated"] += 1
                continue

            try:
                allocation = PaymentAllocation(
                    payment_id=payment.payment_id,
                    invoice_id=invoice.invoice_id,
                    allocated_amount=payment.amount,
                    allocation_date=payment.payment_date,
                )
                self.db.add(allocation)

                invoice.amount_paid = min(
                    invoice.total_amount,
                    invoice.amount_paid + payment.amount,
                )
                self._set_invoice_status_from_amount_paid(invoice)

                results["resolved"] += 1
                logger.info(
                    "Ledger-resolved: payment %s "
                    "(Splynx %d) -> invoice %s "
                    "(Splynx inv %d)",
                    payment.payment_id,
                    txn.document_id,
                    invoice.invoice_number,
                    txn.invoice_id,
                )
            except Exception as exc:
                logger.exception(
                    "Error resolving payment %s from ledger: %s",
                    payment.payment_id,
                    exc,
                )
                results["errors"].append(f"Payment {payment.payment_id}: {exc}")

        self.db.flush()

        still_unresolved = len(splynx_id_to_payment)
        logger.info(
            "Ledger resolution complete: %d resolved, "
            "%d invoice not found, %d no ledger link, "
            "%d still unresolved",
            results["resolved"],
            results["invoice_not_found"],
            results["no_ledger_link"],
            still_unresolved,
        )
        return results

    def post_unposted_payments(self) -> dict[str, int]:
        """Post GL journal entries for CLEARED payments that lack them."""
        from app.services.finance.ar.customer_payment import (
            CustomerPaymentService,
        )

        unposted = list(
            self.db.scalars(
                select(CustomerPayment).where(
                    CustomerPayment.organization_id == self.organization_id,
                    CustomerPayment.splynx_id.isnot(None),
                    CustomerPayment.status == PaymentStatus.CLEARED,
                    CustomerPayment.journal_entry_id.is_(None),
                    CustomerPayment.amount > 0,
                )
            ).all()
        )
        if not unposted:
            return {"posted": 0, "failed": 0, "skipped": 0}

        logger.info(
            "Posting GL journals for %d unposted Splynx payments",
            len(unposted),
        )
        posted = 0
        failed = 0
        skipped = 0

        for payment in unposted:
            try:
                if CustomerPaymentService.ensure_gl_posted(self.db, payment):
                    posted += 1
                else:
                    skipped += 1
            except Exception:
                logger.exception(
                    "GL posting failed for payment %s",
                    payment.payment_id,
                )
                failed += 1

        self.db.flush()
        logger.info(
            "GL posting complete: %d posted, %d failed, %d skipped",
            posted,
            failed,
            skipped,
        )
        return {
            "posted": posted,
            "failed": failed,
            "skipped": skipped,
        }

    def _set_invoice_status_from_amount_paid(self, invoice: Invoice) -> None:
        """Set invoice status from amount_paid."""
        if invoice.amount_paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        elif invoice.amount_paid > Decimal("0"):
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        else:
            invoice.status = InvoiceStatus.POSTED

    def _recompute_invoice_paid_from_allocations(self, invoice: Invoice) -> Decimal:
        """Recompute invoice.amount_paid from all allocations."""
        total_allocated = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(PaymentAllocation.allocated_amount),
                    0,
                )
            ).where(PaymentAllocation.invoice_id == invoice.invoice_id)
        )
        allocated = Decimal(str(total_allocated or 0))
        invoice.amount_paid = min(invoice.total_amount, allocated)
        self._set_invoice_status_from_amount_paid(invoice)
        return allocated

    def repair_payment_invoice_relationships(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        batch_size: int | None = None,
    ) -> dict[str, Any]:
        """Repair payment->invoice allocations using Splynx links."""
        summary: dict[str, Any] = {
            "processed": 0,
            "already_correct": 0,
            "fixed": 0,
            "created_allocations": 0,
            "relinked_allocations": 0,
            "updated_amounts": 0,
            "no_invoice_link": 0,
            "missing_local_payment": 0,
            "missing_local_invoice": 0,
            "customer_mismatch": 0,
            "overallocated_invoices": 0,
            "errors": [],
        }

        touched_invoice_ids: set[UUID] = set()
        processed = 0
        for splynx_payment in self.client.get_payments(
            date_from=date_from,
            date_to=date_to,
        ):
            if batch_size and processed >= batch_size:
                break
            processed += 1
            summary["processed"] += 1

            try:
                if not splynx_payment.invoice_id:
                    summary["no_invoice_link"] += 1
                    continue

                payment = self.db.scalar(
                    select(CustomerPayment).where(
                        CustomerPayment.organization_id == self.organization_id,
                        CustomerPayment.splynx_id == str(splynx_payment.id),
                    )
                )
                if not payment:
                    summary["missing_local_payment"] += 1
                    continue

                invoice = self.db.scalar(
                    select(Invoice).where(
                        Invoice.organization_id == self.organization_id,
                        Invoice.splynx_id == str(splynx_payment.invoice_id),
                    )
                )
                if not invoice:
                    invoice = self.db.scalar(
                        select(Invoice).where(
                            Invoice.organization_id == self.organization_id,
                            Invoice.correlation_id
                            == f"splynx-inv-{splynx_payment.invoice_id}",
                        )
                    )
                if not invoice:
                    summary["missing_local_invoice"] += 1
                    continue

                if payment.customer_id != invoice.customer_id:
                    summary["customer_mismatch"] += 1
                    continue

                allocation_date = (
                    self._parse_date(splynx_payment.date) or payment.payment_date
                )
                existing_allocation = self.db.scalar(
                    select(PaymentAllocation).where(
                        PaymentAllocation.payment_id == payment.payment_id
                    )
                )

                if existing_allocation:
                    allocation_matches = (
                        existing_allocation.invoice_id == invoice.invoice_id
                        and existing_allocation.allocated_amount
                        == splynx_payment.amount
                        and existing_allocation.allocation_date == allocation_date
                    )
                    if allocation_matches:
                        summary["already_correct"] += 1
                        continue

                    touched_invoice_ids.add(existing_allocation.invoice_id)
                    if existing_allocation.invoice_id != invoice.invoice_id:
                        summary["relinked_allocations"] += 1
                    if existing_allocation.allocated_amount != splynx_payment.amount:
                        summary["updated_amounts"] += 1

                    existing_allocation.invoice_id = invoice.invoice_id
                    existing_allocation.allocated_amount = splynx_payment.amount
                    existing_allocation.allocation_date = allocation_date
                    touched_invoice_ids.add(invoice.invoice_id)
                    summary["fixed"] += 1
                    continue

                self.db.add(
                    PaymentAllocation(
                        payment_id=payment.payment_id,
                        invoice_id=invoice.invoice_id,
                        allocated_amount=splynx_payment.amount,
                        allocation_date=allocation_date,
                    )
                )
                touched_invoice_ids.add(invoice.invoice_id)
                summary["created_allocations"] += 1
                summary["fixed"] += 1
            except Exception as exc:
                logger.exception(
                    "Relationship repair error for Splynx payment %s: %s",
                    splynx_payment.id,
                    exc,
                )
                summary["errors"].append(f"Payment {splynx_payment.id}: {exc}")

        for invoice_id in touched_invoice_ids:
            invoice = self.db.get(Invoice, invoice_id)
            if not invoice:
                continue
            allocated_total = self._recompute_invoice_paid_from_allocations(invoice)
            if allocated_total > invoice.total_amount:
                summary["overallocated_invoices"] += 1

        self.db.flush()
        logger.info("Splynx relationship repair summary: %s", summary)
        return summary
