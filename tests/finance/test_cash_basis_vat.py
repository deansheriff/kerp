"""Tests for cash-basis VAT/WHT/revenue helpers in rpt.common."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.finance.rpt.common import _prorate


class TestProrate:
    def test_basic_proration(self):
        # 100 allocated against an invoice of 1000 with 75 VAT → 7.5
        assert _prorate(Decimal("100"), Decimal("75"), Decimal("1000")) == Decimal(
            "7.5"
        )

    def test_full_allocation(self):
        # Allocating the entire invoice returns the entire component
        assert _prorate(Decimal("1000"), Decimal("75"), Decimal("1000")) == Decimal(
            "75"
        )

    def test_zero_allocated(self):
        assert _prorate(Decimal("0"), Decimal("75"), Decimal("1000")) == Decimal("0")

    def test_zero_component(self):
        # Zero-rated invoice
        assert _prorate(Decimal("100"), Decimal("0"), Decimal("1000")) == Decimal("0")

    def test_zero_total_does_not_divide_by_zero(self):
        assert _prorate(Decimal("100"), Decimal("75"), Decimal("0")) == Decimal("0")

    def test_none_allocated_safe(self):
        assert _prorate(None, Decimal("75"), Decimal("1000")) == Decimal("0")

    def test_none_component_safe(self):
        assert _prorate(Decimal("100"), None, Decimal("1000")) == Decimal("0")

    def test_none_total_safe(self):
        assert _prorate(Decimal("100"), Decimal("75"), None) == Decimal("0")

    def test_partial_allocation(self):
        # 50% of an invoice with 7.5% VAT → 50% of the VAT
        # Invoice: subtotal 1000, VAT 75, total 1075
        # Pay 537.5 → VAT portion = 537.5 * 75 / 1075 = 37.5
        result = _prorate(Decimal("537.5"), Decimal("75"), Decimal("1075"))
        assert result == Decimal("37.5")

    def test_inclusive_vat_invoice(self):
        # VAT-inclusive invoice: subtotal 1000, VAT 75, total 1075
        # Pay 1075 → VAT = 75 (full); subtotal = 1000 (full)
        assert _prorate(Decimal("1075"), Decimal("75"), Decimal("1075")) == Decimal(
            "75"
        )
        assert _prorate(Decimal("1075"), Decimal("1000"), Decimal("1075")) == Decimal(
            "1000"
        )


class TestCashBasisVATTotalsShape:
    """Shape and aggregation logic for _cash_basis_vat_totals.

    Uses MagicMock for the SQL execution so we exercise the in-Python
    aggregation without requiring a live DB.
    """

    def _make_db_with_rows(self, ar_rows, ap_rows):
        db = MagicMock()

        # First call (AR), second call (AP). db.execute returns an object
        # with .all() returning the rows.
        ar_result = MagicMock()
        ar_result.all.return_value = ar_rows
        ap_result = MagicMock()
        ap_result.all.return_value = ap_rows
        db.execute.side_effect = [ar_result, ap_result]
        return db

    def _ar_row(self, allocated, sub, tax, total, *, invoice_type="STANDARD"):
        from app.models.finance.ar.invoice import InvoiceType

        type_value = (
            InvoiceType.CREDIT_NOTE
            if invoice_type == "CREDIT_NOTE"
            else InvoiceType.STANDARD
        )
        return SimpleNamespace(
            allocation_date=None,
            customer_id=None,
            invoice_id=None,
            invoice_type=type_value,
            invoice_subtotal=Decimal(sub),
            invoice_tax=Decimal(tax),
            invoice_total=Decimal(total),
            allocated_amount=Decimal(allocated),
        )

    def _ap_row(self, allocated, sub, tax, total):
        return SimpleNamespace(
            allocation_date=None,
            supplier_id=None,
            invoice_id=None,
            invoice_subtotal=Decimal(sub),
            invoice_tax=Decimal(tax),
            invoice_total=Decimal(total),
            allocated_amount=Decimal(allocated),
        )

    def test_single_full_receipt_yields_full_vat(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        ar_rows = [self._ar_row("1075", "1000", "75", "1075")]
        ap_rows = []
        db = self._make_db_with_rows(ar_rows, ap_rows)

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        assert totals["output_vat"] == Decimal("75")
        assert totals["output_base"] == Decimal("1000")
        assert totals["input_vat"] == Decimal("0")
        assert totals["net_vat_payable"] == Decimal("75")

    def test_partial_receipt_prorated(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        # 50% receipt → 50% of VAT
        ar_rows = [self._ar_row("537.5", "1000", "75", "1075")]
        db = self._make_db_with_rows(ar_rows, [])

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        assert totals["output_vat"] == Decimal("37.5")
        assert totals["output_base"] == Decimal("500")

    def test_credit_note_reduces_output(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        ar_rows = [
            self._ar_row("1075", "1000", "75", "1075"),
            self._ar_row("215", "200", "15", "215", invoice_type="CREDIT_NOTE"),
        ]
        db = self._make_db_with_rows(ar_rows, [])

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        assert totals["output_vat"] == Decimal("75")
        assert totals["output_credit_notes_vat"] == Decimal("15")
        assert totals["net_output_vat"] == Decimal("60")

    def test_zero_rated_receipt_lands_in_zero_rated_bucket(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        # invoice with tax_amount=0 (zero-rated)
        ar_rows = [self._ar_row("500", "500", "0", "500")]
        db = self._make_db_with_rows(ar_rows, [])

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        assert totals["output_vat"] == Decimal("0")
        assert totals["output_zero_rated"] == Decimal("500")
        assert totals["output_base"] == Decimal("0")

    def test_input_vat_aggregates_supplier_payments(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        ap_rows = [self._ap_row("1075", "1000", "75", "1075")]
        db = self._make_db_with_rows([], ap_rows)

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        assert totals["input_vat"] == Decimal("75")
        assert totals["input_base"] == Decimal("1000")
        # No output → net payable is negative (refund position)
        assert totals["net_vat_payable"] == Decimal("-75")

    def test_net_vat_payable_full_cycle(self):
        from datetime import date

        from app.services.finance.rpt.common import _cash_basis_vat_totals

        # Output: 100 VAT collected; CN: 10 reversed; Input: 30 paid
        ar_rows = [
            self._ar_row("1433.33", "1333.33", "100", "1433.33"),
            self._ar_row(
                "143.33", "133.33", "10", "143.33", invoice_type="CREDIT_NOTE"
            ),
        ]
        ap_rows = [self._ap_row("430", "400", "30", "430")]
        db = self._make_db_with_rows(ar_rows, ap_rows)

        totals = _cash_basis_vat_totals(
            db,
            "00000000-0000-0000-0000-000000000001",
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        # net payable = (100 - 10) - 30 = 60
        assert totals["net_vat_payable"] == Decimal("60")
