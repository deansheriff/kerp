"""
Tax control tracker aggregation service.

Builds a control-oriented VAT/WHT tracker from the strongest available source
for each metric instead of relying on a single tax transaction layer.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.common import coerce_uuid


ZERO = Decimal("0")
EVIDENCE_STATUS_OPTIONS = ("MISSING", "REQUESTED", "RECEIVED", "VERIFIED")
CUSTOMER_CERT_EVIDENCE = "CUSTOMER_WHT_CERTIFICATE"
SUPPLIER_REMIT_EVIDENCE = "SUPPLIER_WHT_REMITTANCE"


@dataclass
class SourceDefinition:
    title: str
    source: str
    use_for: str
    caveat: str


@dataclass
class SummaryMetric:
    title: str
    value: Decimal
    source: str
    note: str


@dataclass
class MonthlyVATRow:
    month_start: date
    ar_output_vat: Decimal = ZERO
    ap_input_vat: Decimal = ZERO
    customer_vat_withheld: Decimal = ZERO
    gl_vat_payable: Decimal = ZERO
    gl_input_vat: Decimal = ZERO

    @property
    def erp_net_vat(self) -> Decimal:
        return self.ar_output_vat - self.ap_input_vat - self.customer_vat_withheld

    @property
    def gl_net_vat(self) -> Decimal:
        return self.gl_vat_payable - self.gl_input_vat - self.customer_vat_withheld

    @property
    def variance(self) -> Decimal:
        return self.erp_net_vat - self.gl_net_vat


@dataclass
class MonthlyWHTRow:
    month_start: date
    ap_supplier_wht: Decimal = ZERO
    customer_wht_receivable: Decimal = ZERO
    gl_wht_liability: Decimal = ZERO

    @property
    def variance(self) -> Decimal:
        return self.ap_supplier_wht - self.gl_wht_liability


@dataclass
class EvidenceStatus:
    label: str
    status: str
    detail: str
    source: str


@dataclass
class CustomerDeductionRow:
    customer_id: UUID
    customer_name: str
    vat_withheld: Decimal = ZERO
    wht_receivable: Decimal = ZERO
    receipt_count: int = 0
    certificate_count: int = 0
    evidence_status: str = "MISSING"
    evidence_reference: str = ""
    evidence_notes: str = ""

    @property
    def combined_total(self) -> Decimal:
        return self.vat_withheld + self.wht_receivable


@dataclass
class SupplierWHTRow:
    supplier_id: UUID
    supplier_name: str
    input_vat: Decimal = ZERO
    withheld_wht: Decimal = ZERO
    invoice_count: int = 0
    payment_wht_count: int = 0
    evidence_status: str = "MISSING"
    evidence_reference: str = ""
    evidence_notes: str = ""


@dataclass
class TrackerCounts:
    vat_return_total: int = 0
    vat_return_filed: int = 0
    vat_return_draft: int = 0
    vat_return_paid: int = 0
    sales_invoice_withholding_fields: int = 0
    customer_payment_wht_fields: int = 0
    customer_payment_wht_certificates: int = 0
    supplier_payment_wht_fields: int = 0
    customer_deduction_gl_hits: int = 0
    backfilled_ar_invoice_count: int = 0
    backfilled_ap_invoice_count: int = 0


@dataclass
class TaxControlTrackerData:
    year: int
    start_date: date
    end_date: date
    source_map: list[SourceDefinition]
    summary_metrics: list[SummaryMetric]
    monthly_vat_rows: list[MonthlyVATRow]
    monthly_wht_rows: list[MonthlyWHTRow]
    evidence_statuses: list[EvidenceStatus]
    top_customer_deductions: list[CustomerDeductionRow]
    top_supplier_wht: list[SupplierWHTRow]
    counts: TrackerCounts


def _month_starts(year: int) -> list[date]:
    return [date(year, month, 1) for month in range(1, 13)]


def _decimal(value: Any) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class TaxControlTrackerService:
    """Aggregate VAT/WHT control data across AR, AP, GL, and tax workflow."""

    VAT_GL_ACCOUNTS = ("2120", "1440", "4031")
    WHT_GL_ACCOUNTS = ("2110", "1420")

    @staticmethod
    def upsert_evidence(
        db: Session,
        organization_id: UUID | str,
        year: int,
        evidence_type: str,
        entity_type: str,
        entity_id: UUID | str,
        status: str,
        reference: str | None,
        notes: str | None,
        updated_by_user_id: UUID | str | None,
    ) -> None:
        org_id = coerce_uuid(organization_id)
        ent_id = coerce_uuid(entity_id)
        user_id = coerce_uuid(updated_by_user_id) if updated_by_user_id else None
        normalized_status = (status or "MISSING").upper()
        if normalized_status not in EVIDENCE_STATUS_OPTIONS:
            normalized_status = "MISSING"

        db.execute(
            text(
                """
                INSERT INTO tax.control_evidence (
                    organization_id,
                    evidence_year,
                    evidence_type,
                    entity_type,
                    entity_id,
                    status,
                    reference,
                    notes,
                    updated_by_user_id
                )
                VALUES (
                    :organization_id,
                    :evidence_year,
                    :evidence_type,
                    :entity_type,
                    :entity_id,
                    :status,
                    NULLIF(:reference, ''),
                    NULLIF(:notes, ''),
                    :updated_by_user_id
                )
                ON CONFLICT (
                    organization_id,
                    evidence_year,
                    evidence_type,
                    entity_type,
                    entity_id
                )
                DO UPDATE SET
                    status = EXCLUDED.status,
                    reference = EXCLUDED.reference,
                    notes = EXCLUDED.notes,
                    updated_by_user_id = EXCLUDED.updated_by_user_id,
                    updated_at = now()
                """
            ),
            {
                "organization_id": org_id,
                "evidence_year": year,
                "evidence_type": evidence_type,
                "entity_type": entity_type,
                "entity_id": ent_id,
                "status": normalized_status,
                "reference": (reference or "").strip(),
                "notes": (notes or "").strip(),
                "updated_by_user_id": user_id,
            },
        )
        db.commit()

    @staticmethod
    def build(
        db: Session,
        organization_id: UUID | str,
        year: int,
    ) -> TaxControlTrackerData:
        org_id = coerce_uuid(organization_id)
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        monthly_vat = {
            month: MonthlyVATRow(month_start=month) for month in _month_starts(year)
        }
        monthly_wht = {
            month: MonthlyWHTRow(month_start=month) for month in _month_starts(year)
        }

        ar_output_vat = ZERO
        ap_input_vat = ZERO
        ap_supplier_wht = ZERO
        customer_vat_withheld = ZERO
        customer_wht_receivable = ZERO
        gl_vat_payable = ZERO
        gl_input_vat = ZERO
        gl_wht_liability = ZERO

        for row in db.execute(
            text(
                """
                SELECT date_trunc('month', invoice_date)::date AS month_start,
                       COALESCE(SUM(tax_amount), 0) AS output_vat
                FROM ar.invoice
                WHERE organization_id = :org_id
                  AND invoice_date BETWEEN :start_date AND :end_date
                  AND status IN ('POSTED', 'PARTIALLY_PAID', 'PAID', 'OVERDUE')
                GROUP BY 1
                ORDER BY 1
                """
            ),
            {"org_id": org_id, "start_date": start_date, "end_date": end_date},
        ):
            month_start = row.month_start
            amount = _decimal(row.output_vat)
            if month_start in monthly_vat:
                monthly_vat[month_start].ar_output_vat = amount
            ar_output_vat += amount

        for row in db.execute(
            text(
                """
                SELECT date_trunc('month', invoice_date)::date AS month_start,
                       COALESCE(SUM(tax_amount), 0) AS input_vat,
                       COALESCE(SUM(withholding_tax_amount), 0) AS supplier_wht
                FROM ap.supplier_invoice
                WHERE organization_id = :org_id
                  AND invoice_date BETWEEN :start_date AND :end_date
                  AND status IN ('POSTED', 'PARTIALLY_PAID', 'PAID')
                GROUP BY 1
                ORDER BY 1
                """
            ),
            {"org_id": org_id, "start_date": start_date, "end_date": end_date},
        ):
            month_start = row.month_start
            input_vat = _decimal(row.input_vat)
            supplier_wht = _decimal(row.supplier_wht)
            if month_start in monthly_vat:
                monthly_vat[month_start].ap_input_vat = input_vat
            if month_start in monthly_wht:
                monthly_wht[month_start].ap_supplier_wht = supplier_wht
            ap_input_vat += input_vat
            ap_supplier_wht += supplier_wht

        for row in db.execute(
            text(
                """
                SELECT date_trunc('month', posting_date)::date AS month_start,
                       account_code,
                       COALESCE(SUM(debit_amount), 0) AS debit_total,
                       COALESCE(SUM(credit_amount), 0) AS credit_total
                FROM gl.posted_ledger_line
                WHERE organization_id = :org_id
                  AND posting_date BETWEEN :start_date AND :end_date
                  AND account_code IN ('2120', '1440', '4031', '2110', '1420')
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            ),
            {"org_id": org_id, "start_date": start_date, "end_date": end_date},
        ):
            month_start = row.month_start
            debit_total = _decimal(row.debit_total)
            credit_total = _decimal(row.credit_total)
            movement = ZERO

            if row.account_code in {"2120", "2110", "4031"}:
                movement = credit_total - debit_total
            elif row.account_code in {"1440", "1420"}:
                movement = debit_total - credit_total

            if row.account_code == "2120":
                monthly_vat[month_start].gl_vat_payable = movement
                gl_vat_payable += movement
            elif row.account_code == "1440":
                monthly_vat[month_start].gl_input_vat = movement
                gl_input_vat += movement
            elif row.account_code == "4031":
                monthly_vat[month_start].customer_vat_withheld = movement
                customer_vat_withheld += movement
            elif row.account_code == "2110":
                monthly_wht[month_start].gl_wht_liability = movement
                gl_wht_liability += movement
            elif row.account_code == "1420":
                monthly_wht[month_start].customer_wht_receivable = movement
                customer_wht_receivable += movement

        counts_row = db.execute(
            text(
                """
                WITH vat_returns AS (
                    SELECT
                        COUNT(*) FILTER (WHERE tr.return_type = 'VAT') AS total_count,
                        COUNT(*) FILTER (WHERE tr.return_type = 'VAT' AND tr.status = 'FILED') AS filed_count,
                        COUNT(*) FILTER (WHERE tr.return_type = 'VAT' AND tr.status = 'DRAFT') AS draft_count,
                        COUNT(*) FILTER (WHERE tr.return_type = 'VAT' AND tr.is_paid IS TRUE) AS paid_count
                    FROM tax.tax_return tr
                    JOIN tax.tax_period tp ON tp.period_id = tr.tax_period_id
                    WHERE tr.organization_id = :org_id
                      AND tp.start_date <= :end_date
                      AND tp.end_date >= :start_date
                ),
                sales_invoice_flags AS (
                    SELECT COUNT(*) AS count_value
                    FROM ar.invoice
                    WHERE organization_id = :org_id
                      AND invoice_date BETWEEN :start_date AND :end_date
                      AND (
                        COALESCE(withholding_tax_amount, 0) <> 0
                        OR COALESCE(vat_withheld, FALSE) IS TRUE
                      )
                ),
                customer_payment_wht AS (
                    SELECT
                        COUNT(*) FILTER (WHERE COALESCE(wht_amount, 0) <> 0) AS wht_count,
                        COUNT(*) FILTER (
                            WHERE COALESCE(NULLIF(TRIM(wht_certificate_number), ''), '') <> ''
                        ) AS cert_count
                    FROM ar.customer_payment
                    WHERE organization_id = :org_id
                      AND payment_date BETWEEN :start_date AND :end_date
                ),
                supplier_payment_wht AS (
                    SELECT COUNT(*) AS count_value
                    FROM ap.supplier_payment
                    WHERE organization_id = :org_id
                      AND payment_date BETWEEN :start_date AND :end_date
                      AND status NOT IN ('VOID', 'REJECTED')
                      AND COALESCE(withholding_tax_amount, 0) <> 0
                ),
                customer_gl_deductions AS (
                    SELECT COUNT(*) AS count_value
                    FROM gl.posted_ledger_line
                    WHERE organization_id = :org_id
                      AND posting_date BETWEEN :start_date AND :end_date
                      AND account_code IN ('4031', '1420')
                      AND source_module = 'AR'
                ),
                backfilled_ar AS (
                    SELECT COUNT(*) AS count_value
                    FROM ar.invoice
                    WHERE organization_id = :org_id
                      AND invoice_date BETWEEN :start_date AND :end_date
                      AND created_at::date > :end_date
                ),
                backfilled_ap AS (
                    SELECT COUNT(*) AS count_value
                    FROM ap.supplier_invoice
                    WHERE organization_id = :org_id
                      AND invoice_date BETWEEN :start_date AND :end_date
                      AND created_at::date > :end_date
                )
                SELECT
                    vr.total_count,
                    vr.filed_count,
                    vr.draft_count,
                    vr.paid_count,
                    sif.count_value AS sales_invoice_withholding_fields,
                    cpw.wht_count AS customer_payment_wht_fields,
                    cpw.cert_count AS customer_payment_wht_certificates,
                    spw.count_value AS supplier_payment_wht_fields,
                    cgd.count_value AS customer_deduction_gl_hits,
                    bar.count_value AS backfilled_ar_invoice_count,
                    bap.count_value AS backfilled_ap_invoice_count
                FROM vat_returns vr
                CROSS JOIN sales_invoice_flags sif
                CROSS JOIN customer_payment_wht cpw
                CROSS JOIN supplier_payment_wht spw
                CROSS JOIN customer_gl_deductions cgd
                CROSS JOIN backfilled_ar bar
                CROSS JOIN backfilled_ap bap
                """
            ),
            {"org_id": org_id, "start_date": start_date, "end_date": end_date},
        ).one()

        counts = TrackerCounts(
            vat_return_total=int(counts_row.total_count or 0),
            vat_return_filed=int(counts_row.filed_count or 0),
            vat_return_draft=int(counts_row.draft_count or 0),
            vat_return_paid=int(counts_row.paid_count or 0),
            sales_invoice_withholding_fields=int(
                counts_row.sales_invoice_withholding_fields or 0
            ),
            customer_payment_wht_fields=int(
                counts_row.customer_payment_wht_fields or 0
            ),
            customer_payment_wht_certificates=int(
                counts_row.customer_payment_wht_certificates or 0
            ),
            supplier_payment_wht_fields=int(
                counts_row.supplier_payment_wht_fields or 0
            ),
            customer_deduction_gl_hits=int(counts_row.customer_deduction_gl_hits or 0),
            backfilled_ar_invoice_count=int(
                counts_row.backfilled_ar_invoice_count or 0
            ),
            backfilled_ap_invoice_count=int(
                counts_row.backfilled_ap_invoice_count or 0
            ),
        )

        evidence_rows = list(
            db.execute(
                text(
                    """
                    SELECT evidence_type, entity_type, entity_id, status, COALESCE(reference, '') AS reference,
                           COALESCE(notes, '') AS notes
                    FROM tax.control_evidence
                    WHERE organization_id = :org_id
                      AND evidence_year = :evidence_year
                      AND evidence_type IN (:customer_type, :supplier_type)
                    """
                ),
                {
                    "org_id": org_id,
                    "evidence_year": year,
                    "customer_type": CUSTOMER_CERT_EVIDENCE,
                    "supplier_type": SUPPLIER_REMIT_EVIDENCE,
                },
            )
        )
        evidence_map = {
            (row.evidence_type, row.entity_type, row.entity_id): row
            for row in evidence_rows
        }

        top_customer_deductions = [
            CustomerDeductionRow(
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                vat_withheld=_decimal(row.vat_withheld),
                wht_receivable=_decimal(row.wht_receivable),
                receipt_count=int(row.receipt_count or 0),
                certificate_count=int(row.certificate_count or 0),
                evidence_status=(
                    evidence_map[
                        (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    ].status
                    if (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    in evidence_map
                    else "MISSING"
                ),
                evidence_reference=(
                    evidence_map[
                        (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    ].reference
                    if (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    in evidence_map
                    else ""
                ),
                evidence_notes=(
                    evidence_map[
                        (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    ].notes
                    if (CUSTOMER_CERT_EVIDENCE, "CUSTOMER", row.customer_id)
                    in evidence_map
                    else ""
                ),
            )
            for row in db.execute(
                text(
                    """
                    SELECT
                        c.customer_id,
                        COALESCE(NULLIF(c.trading_name, ''), c.legal_name) AS customer_name,
                        COALESCE(SUM(CASE WHEN pll.account_code = '4031'
                            THEN pll.debit_amount - pll.credit_amount
                            ELSE 0 END), 0) AS vat_withheld,
                        COALESCE(SUM(CASE WHEN pll.account_code = '1420'
                            THEN pll.debit_amount - pll.credit_amount
                            ELSE 0 END), 0) AS wht_receivable,
                        COUNT(DISTINCT cp.payment_id) AS receipt_count,
                        COUNT(DISTINCT CASE
                            WHEN COALESCE(NULLIF(TRIM(cp.wht_certificate_number), ''), '') <> ''
                            THEN cp.payment_id
                            ELSE NULL
                        END) AS certificate_count
                    FROM gl.posted_ledger_line pll
                    JOIN ar.customer_payment cp
                      ON cp.payment_number = pll.journal_reference
                     AND cp.organization_id = pll.organization_id
                    JOIN ar.customer c
                      ON c.customer_id = cp.customer_id
                     AND c.organization_id = cp.organization_id
                    WHERE pll.organization_id = :org_id
                      AND pll.posting_date BETWEEN :start_date AND :end_date
                      AND pll.account_code IN ('4031', '1420')
                      AND pll.source_module = 'ar'
                    GROUP BY c.customer_id, customer_name
                    HAVING COALESCE(SUM(CASE WHEN pll.account_code = '4031'
                        THEN pll.debit_amount - pll.credit_amount
                        ELSE 0 END), 0) <> 0
                        OR COALESCE(SUM(CASE WHEN pll.account_code = '1420'
                        THEN pll.debit_amount - pll.credit_amount
                        ELSE 0 END), 0) <> 0
                    ORDER BY
                        (
                            COALESCE(SUM(CASE WHEN pll.account_code = '4031'
                                THEN pll.debit_amount - pll.credit_amount
                                ELSE 0 END), 0)
                            +
                            COALESCE(SUM(CASE WHEN pll.account_code = '1420'
                                THEN pll.debit_amount - pll.credit_amount
                                ELSE 0 END), 0)
                        ) DESC,
                        customer_name
                    LIMIT 15
                    """
                ),
                {"org_id": org_id, "start_date": start_date, "end_date": end_date},
            )
        ]

        top_supplier_wht = [
            SupplierWHTRow(
                supplier_id=row.supplier_id,
                supplier_name=row.supplier_name,
                input_vat=_decimal(row.input_vat),
                withheld_wht=_decimal(row.withheld_wht),
                invoice_count=int(row.invoice_count or 0),
                payment_wht_count=int(row.payment_wht_count or 0),
                evidence_status=(
                    evidence_map[
                        (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    ].status
                    if (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    in evidence_map
                    else "MISSING"
                ),
                evidence_reference=(
                    evidence_map[
                        (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    ].reference
                    if (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    in evidence_map
                    else ""
                ),
                evidence_notes=(
                    evidence_map[
                        (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    ].notes
                    if (SUPPLIER_REMIT_EVIDENCE, "SUPPLIER", row.supplier_id)
                    in evidence_map
                    else ""
                ),
            )
            for row in db.execute(
                text(
                    """
                    WITH payment_wht AS (
                        SELECT
                            supplier_id,
                            COUNT(*) FILTER (
                                WHERE COALESCE(withholding_tax_amount, 0) <> 0
                                  AND status IN ('SENT', 'CLEARED')
                            ) AS payment_wht_count
                        FROM ap.supplier_payment
                        WHERE organization_id = :org_id
                          AND payment_date BETWEEN :start_date AND :end_date
                        GROUP BY supplier_id
                    )
                    SELECT
                        s.supplier_id,
                        COALESCE(NULLIF(s.trading_name, ''), s.legal_name) AS supplier_name,
                        COALESCE(SUM(si.tax_amount), 0) AS input_vat,
                        COALESCE(SUM(si.withholding_tax_amount), 0) AS withheld_wht,
                        COUNT(*) AS invoice_count,
                        COALESCE(MAX(pw.payment_wht_count), 0) AS payment_wht_count
                    FROM ap.supplier_invoice si
                    JOIN ap.supplier s
                      ON s.supplier_id = si.supplier_id
                     AND s.organization_id = si.organization_id
                    LEFT JOIN payment_wht pw
                      ON pw.supplier_id = si.supplier_id
                    WHERE si.organization_id = :org_id
                      AND si.invoice_date BETWEEN :start_date AND :end_date
                      AND si.status IN ('POSTED', 'PARTIALLY_PAID', 'PAID')
                      AND (
                        COALESCE(si.tax_amount, 0) <> 0
                        OR COALESCE(si.withholding_tax_amount, 0) <> 0
                      )
                    GROUP BY s.supplier_id, supplier_name
                    ORDER BY COALESCE(SUM(si.withholding_tax_amount), 0) DESC, supplier_name
                    LIMIT 15
                    """
                ),
                {"org_id": org_id, "start_date": start_date, "end_date": end_date},
            )
        ]

        source_map = [
            SourceDefinition(
                title="VAT filing basis",
                source="AR invoices and AP supplier invoices",
                use_for="Output VAT, input VAT, purchase-side WHT withheld by us",
                caveat="Best source for taxable transaction basis; not proof of filing or payment.",
            ),
            SourceDefinition(
                title="Customer deduction basis",
                source="GL posted receipt journals on 4031 and 1420",
                use_for="VAT withheld at source and WHT deducted against us",
                caveat="AR invoice and payment tax fields are not populated reliably for 2025.",
            ),
            SourceDefinition(
                title="GL control basis",
                source="gl.posted_ledger_line on 2120, 1440, 2110, 4031, 1420",
                use_for="Monthly control totals and movement checks",
                caveat="Useful for reconciliation; not the primary filing basis.",
            ),
            SourceDefinition(
                title="Workflow evidence",
                source="tax_return plus payment field coverage counts",
                use_for="Return status visibility and evidence-gap flags",
                caveat="External TaxPro/FIRS acknowledgements and wallet-credit support still sit outside ERP.",
            ),
        ]

        summary_metrics = [
            SummaryMetric(
                title="Sales output VAT",
                value=ar_output_vat,
                source="AR invoices",
                note="Invoice-date basis from posted AR invoices.",
            ),
            SummaryMetric(
                title="Purchase input VAT",
                value=ap_input_vat,
                source="AP invoices",
                note="Invoice-date basis from posted supplier invoices.",
            ),
            SummaryMetric(
                title="VAT withheld against us",
                value=customer_vat_withheld,
                source="GL 4031",
                note="Customer-side deductions evidenced on receipt journals.",
            ),
            SummaryMetric(
                title="Supplier WHT withheld by us",
                value=ap_supplier_wht,
                source="AP invoices",
                note="Operational WHT withheld on supplier transactions.",
            ),
            SummaryMetric(
                title="Customer WHT receivable",
                value=customer_wht_receivable,
                source="GL 1420",
                note="WHT deducted by customers and carried as receivable.",
            ),
            SummaryMetric(
                title="VAT returns stored in ERP",
                value=Decimal(counts.vat_return_total),
                source="tax_return",
                note=f"{counts.vat_return_filed} filed, {counts.vat_return_draft} draft, {counts.vat_return_paid} marked paid.",
            ),
        ]

        evidence_statuses = [
            EvidenceStatus(
                label="VAT return workflow in ERP",
                status="ok" if counts.vat_return_filed > 0 else "warn",
                detail=(
                    f"{counts.vat_return_total} VAT returns stored; "
                    f"{counts.vat_return_filed} filed and {counts.vat_return_draft} still draft."
                ),
                source="tax.tax_return",
            ),
            EvidenceStatus(
                label="Sales-side withholding fields",
                status="warn" if counts.sales_invoice_withholding_fields == 0 else "ok",
                detail=(
                    f"{counts.sales_invoice_withholding_fields} sales invoices carry withholding flags; "
                    "customer deduction support should be read from GL receipt journals."
                ),
                source="ar.invoice",
            ),
            EvidenceStatus(
                label="Customer payment WHT fields",
                status="warn" if counts.customer_payment_wht_fields == 0 else "ok",
                detail=(
                    f"{counts.customer_payment_wht_fields} customer payments carry WHT amounts; "
                    f"{counts.customer_payment_wht_certificates} have certificate numbers."
                ),
                source="ar.customer_payment",
            ),
            EvidenceStatus(
                label="Supplier payment WHT fields",
                status="warn" if counts.supplier_payment_wht_fields == 0 else "ok",
                detail=(
                    f"{counts.supplier_payment_wht_fields} supplier payments carry WHT amounts; "
                    "use AP invoices as the stronger operational basis where this is sparse."
                ),
                source="ap.supplier_payment",
            ),
            EvidenceStatus(
                label="Customer deduction journal coverage",
                status="ok" if counts.customer_deduction_gl_hits > 0 else "warn",
                detail=(
                    f"{counts.customer_deduction_gl_hits} AR-side posted ledger lines hit 4031/1420 in {year}."
                ),
                source="gl.posted_ledger_line",
            ),
            EvidenceStatus(
                label="Backfilled tax-driving invoices",
                status=(
                    "warn"
                    if counts.backfilled_ar_invoice_count > 0
                    or counts.backfilled_ap_invoice_count > 0
                    else "ok"
                ),
                detail=(
                    f"{counts.backfilled_ar_invoice_count} AR invoices and "
                    f"{counts.backfilled_ap_invoice_count} AP invoices dated in {year} were created after year-end."
                ),
                source="ar.invoice / ap.supplier_invoice",
            ),
            EvidenceStatus(
                label="VAT credit evidence",
                status="info",
                detail=(
                    "Wallet-credit and TaxPro filing acknowledgements still require external support; "
                    "the ERP cannot prove them on its own."
                ),
                source="External TaxPro / FIRS evidence",
            ),
        ]

        return TaxControlTrackerData(
            year=year,
            start_date=start_date,
            end_date=end_date,
            source_map=source_map,
            summary_metrics=summary_metrics,
            monthly_vat_rows=list(monthly_vat.values()),
            monthly_wht_rows=list(monthly_wht.values()),
            evidence_statuses=evidence_statuses,
            top_customer_deductions=top_customer_deductions,
            top_supplier_wht=top_supplier_wht,
            counts=counts,
        )

    @staticmethod
    def export_customer_deductions_csv(
        db: Session,
        organization_id: UUID | str,
        year: int,
    ) -> str:
        tracker = TaxControlTrackerService.build(db, organization_id, year)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "year",
                "customer_id",
                "customer_name",
                "vat_withheld",
                "wht_receivable",
                "combined_total",
                "receipt_count",
                "certificate_count",
                "certificate_status",
                "tracker_status",
                "tracker_reference",
                "tracker_notes",
            ]
        )
        for row in tracker.top_customer_deductions:
            writer.writerow(
                [
                    year,
                    str(row.customer_id),
                    row.customer_name,
                    f"{row.vat_withheld:.2f}",
                    f"{row.wht_receivable:.2f}",
                    f"{row.combined_total:.2f}",
                    row.receipt_count,
                    row.certificate_count,
                    "Complete"
                    if row.receipt_count > 0
                    and row.certificate_count >= row.receipt_count
                    else "Missing",
                    row.evidence_status,
                    row.evidence_reference,
                    row.evidence_notes,
                ]
            )
        return output.getvalue()

    @staticmethod
    def export_supplier_wht_csv(
        db: Session,
        organization_id: UUID | str,
        year: int,
    ) -> str:
        tracker = TaxControlTrackerService.build(db, organization_id, year)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "year",
                "supplier_id",
                "supplier_name",
                "input_vat",
                "withheld_wht",
                "invoice_count",
                "payment_wht_count",
                "remittance_status",
                "tracker_status",
                "tracker_reference",
                "tracker_notes",
            ]
        )
        for row in tracker.top_supplier_wht:
            writer.writerow(
                [
                    year,
                    str(row.supplier_id),
                    row.supplier_name,
                    f"{row.input_vat:.2f}",
                    f"{row.withheld_wht:.2f}",
                    row.invoice_count,
                    row.payment_wht_count,
                    "Captured" if row.payment_wht_count > 0 else "Missing",
                    row.evidence_status,
                    row.evidence_reference,
                    row.evidence_notes,
                ]
            )
        return output.getvalue()


tax_control_tracker_service = TaxControlTrackerService()
