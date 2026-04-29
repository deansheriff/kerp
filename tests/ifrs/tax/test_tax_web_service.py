"""
Tests for TaxWebService.
"""

import uuid
from datetime import date, datetime, timezone

try:
    from datetime import UTC  # type: ignore
except ImportError:  # pragma: no cover
    UTC = timezone.utc

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class MockTaxReturn:
    """Mock TaxReturn model for testing."""

    def __init__(self, **kwargs):
        from app.models.finance.tax.tax_return import TaxReturnStatus, TaxReturnType

        self.return_id = kwargs.get("return_id", uuid.uuid4())
        self.tax_period_id = kwargs.get("tax_period_id", uuid.uuid4())
        self.organization_id = kwargs.get("organization_id", uuid.uuid4())
        self.jurisdiction_id = kwargs.get("jurisdiction_id", uuid.uuid4())
        self.return_type = kwargs.get("return_type", TaxReturnType.VAT)
        self.return_reference = kwargs.get("return_reference", "VAT-2024-01")
        self.status = kwargs.get("status", TaxReturnStatus.DRAFT)
        self.total_output_tax = kwargs.get("total_output_tax", Decimal("1000.00"))
        self.total_input_tax = kwargs.get("total_input_tax", Decimal("300.00"))
        self.net_tax_payable = kwargs.get("net_tax_payable", Decimal("700.00"))
        self.adjustments = kwargs.get("adjustments", Decimal("0.00"))
        self.final_amount = kwargs.get("final_amount", Decimal("700.00"))
        self.filed_date = kwargs.get("filed_date")
        self.filing_reference = kwargs.get("filing_reference")
        self.is_paid = kwargs.get("is_paid", False)
        self.payment_date = kwargs.get("payment_date")
        self.payment_reference = kwargs.get("payment_reference")
        self.is_amendment = kwargs.get("is_amendment", False)
        self.original_return_id = kwargs.get("original_return_id")
        self.amendment_reason = kwargs.get("amendment_reason")
        self.prepared_at = kwargs.get("prepared_at")
        self.reviewed_at = kwargs.get("reviewed_at")


class MockBoxValue:
    """Mock TaxReturnBoxValue for testing."""

    def __init__(self, **kwargs):
        self.box_number = kwargs.get("box_number", "1")
        self.description = kwargs.get("description", "Standard Rate Sales")
        self.amount = kwargs.get("amount", Decimal("1000.00"))
        self.transaction_count = kwargs.get("transaction_count", 10)


class MockFormRequest:
    """Minimal request stub for async form handlers."""

    def __init__(self, form_data):
        self._form_data = form_data

    async def form(self):
        return self._form_data


class TestTaxWebServiceHelpers:
    """Tests for helper functions."""

    def test_format_date_with_value(self):
        """Test date formatting with valid date."""
        from app.services.finance.tax.web import _format_date

        result = _format_date(date(2024, 1, 15))
        assert result == "2024-01-15"

    def test_format_date_none(self):
        """Test date formatting with None."""
        from app.services.finance.tax.web import _format_date

        result = _format_date(None)
        assert result == ""

    def test_format_currency_usd(self):
        """Test currency formatting for USD."""
        from app.services.finance.tax.web import _format_currency

        result = _format_currency(Decimal("1234.56"), "USD")
        assert result == "USD 1,234.56"

    def test_format_currency_other(self):
        """Test currency formatting for other currencies."""
        from app.services.finance.tax.web import _format_currency

        result = _format_currency(Decimal("1234.56"), "EUR")
        assert result == "EUR 1,234.56"

    def test_format_currency_none(self):
        """Test currency formatting with None."""
        from app.services.finance.tax.web import _format_currency

        result = _format_currency(None)
        assert result == ""


class TestTaxWebServiceReturnDetail:
    """Tests for return_detail_context method."""

    @patch("app.services.finance.tax.web.tax_return_service")
    def test_return_detail_context_success(self, mock_service):
        """Test successful return detail context."""
        from app.services.finance.tax.web import TaxWebService

        org_id = uuid.uuid4()
        return_id = uuid.uuid4()

        mock_return = MockTaxReturn(
            return_id=return_id,
            organization_id=org_id,
            filed_date=date(2024, 1, 20),
            prepared_at=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
        )
        mock_box_values = [
            MockBoxValue(box_number="1"),
            MockBoxValue(box_number="2"),
        ]

        mock_service.get.return_value = mock_return
        mock_service.get_box_values.return_value = mock_box_values

        mock_db = MagicMock()

        result = TaxWebService.return_detail_context(
            mock_db, str(org_id), str(return_id)
        )

        assert result["tax_return"] is not None
        assert result["tax_return"]["return_id"] == return_id
        assert len(result["box_values"]) == 2

    @patch("app.services.finance.tax.web.tax_return_service")
    def test_return_detail_context_not_found(self, mock_service):
        """Test return detail context with missing return."""
        from app.services.finance.tax.web import TaxWebService

        org_id = uuid.uuid4()
        return_id = uuid.uuid4()

        mock_service.get.return_value = None

        mock_db = MagicMock()

        result = TaxWebService.return_detail_context(
            mock_db, str(org_id), str(return_id)
        )

        assert result["tax_return"] is None
        assert result["box_values"] == []

    @patch("app.services.finance.tax.web.tax_return_service")
    def test_return_detail_context_wrong_org(self, mock_service):
        """Test return detail context with wrong organization."""
        from app.services.finance.tax.web import TaxWebService

        org_id = uuid.uuid4()
        other_org_id = uuid.uuid4()
        return_id = uuid.uuid4()

        mock_return = MockTaxReturn(
            return_id=return_id,
            organization_id=other_org_id,  # Different org
        )

        mock_service.get.return_value = mock_return

        mock_db = MagicMock()

        result = TaxWebService.return_detail_context(
            mock_db, str(org_id), str(return_id)
        )

        assert result["tax_return"] is None
        assert result["box_values"] == []


class TestTaxReturnView:
    """Tests for _tax_return_view function."""

    def test_tax_return_view_complete(self):
        """Test tax return view with all fields."""
        from app.services.finance.tax.web import _tax_return_view

        mock_return = MockTaxReturn(
            filed_date=date(2024, 1, 20),
            filing_reference="FILE-001",
            is_paid=True,
            payment_date=date(2024, 1, 25),
            payment_reference="PAY-001",
            is_amendment=False,
            prepared_at=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            reviewed_at=datetime(2024, 1, 18, 14, 0, tzinfo=UTC),
        )

        result = _tax_return_view(mock_return)

        assert result["return_id"] == mock_return.return_id
        assert result["is_paid"] is True
        assert result["filed_date"] == "2024-01-20"
        assert result["payment_date"] == "2024-01-25"
        assert result["prepared_at"] == "2024-01-15"
        assert result["reviewed_at"] == "2024-01-18"

    def test_tax_return_view_minimal(self):
        """Test tax return view with minimal fields."""
        from app.services.finance.tax.web import _tax_return_view

        mock_return = MockTaxReturn()

        result = _tax_return_view(mock_return)

        assert result["return_id"] == mock_return.return_id
        assert result["filed_date"] == ""
        assert result["prepared_at"] == ""


class TestBoxValueView:
    """Tests for _box_value_view function."""

    def test_box_value_view(self):
        """Test box value view."""
        from app.services.finance.tax.web import _box_value_view

        mock_box = MockBoxValue(
            box_number="1",
            description="Standard Rate Sales",
            amount=Decimal("5000.00"),
            transaction_count=25,
        )

        result = _box_value_view(mock_box)

        assert result["box_number"] == "1"
        assert result["description"] == "Standard Rate Sales"
        assert result["amount"] == "USD 5,000.00"
        assert result["transaction_count"] == 25


class TestTaxCodeFormValidation:
    """Tests for tax code create/update form validation."""

    @pytest.mark.asyncio
    @patch("app.services.finance.tax.web.tax_code_service")
    async def test_create_tax_code_response_surfaces_guardrail_error(
        self, mock_service
    ):
        """Create form should surface service-level VAT/GST account validation errors."""
        from fastapi import HTTPException

        from app.services.finance.tax.web import TaxWebService

        mock_service.create_tax_code.side_effect = HTTPException(
            status_code=400,
            detail="VAT/GST tax codes that apply to sales require a tax collected account",
        )

        service = TaxWebService()
        service.new_tax_code_form_response = MagicMock(return_value="FORM_ERROR")

        request = MockFormRequest(
            {
                "tax_code": "VAT-7.5",
                "tax_name": "VAT 7.5%",
                "tax_type": "VAT",
                "jurisdiction_id": str(uuid.uuid4()),
                "rate_type": "percentage",
                "tax_rate_percentage": "7.5",
                "effective_from": "2026-01-01",
                "is_recoverable": "true",
                "applies_to_sales": "true",
                "applies_to_purchases": "false",
            }
        )
        auth = MagicMock(organization_id=str(uuid.uuid4()))
        db = MagicMock()

        result = await service.create_tax_code_response(request, auth, db)

        assert result == "FORM_ERROR"
        service.new_tax_code_form_response.assert_called_once()
        assert (
            service.new_tax_code_form_response.call_args.kwargs["error"]
            == "VAT/GST tax codes that apply to sales require a tax collected account"
        )

    @pytest.mark.asyncio
    @patch("app.services.finance.tax.web.tax_code_service")
    async def test_update_tax_code_response_validates_missing_paid_account(
        self, mock_service
    ):
        """Edit form should reject recoverable purchase VAT/GST without a paid account."""
        from app.models.finance.tax.tax_code import TaxType
        from app.services.finance.tax.tax_master import TaxCodeService
        from app.services.finance.tax.web import TaxWebService

        existing = MagicMock()
        existing.tax_code = "VAT-7.5 (inclusive)"
        existing.organization_id = uuid.uuid4()
        existing.tax_type = TaxType.VAT
        mock_service.get.return_value = existing
        mock_service.get_by_code.return_value = None
        mock_service.validate_account_mappings.side_effect = (
            TaxCodeService.validate_account_mappings
        )

        service = TaxWebService()
        service.edit_tax_code_form_response = MagicMock(return_value="EDIT_ERROR")

        request = MockFormRequest(
            {
                "tax_code": "VAT-7.5 (inclusive)",
                "tax_name": "VAT 7.5% Inclusive",
                "tax_type": "VAT",
                "jurisdiction_id": str(uuid.uuid4()),
                "rate_type": "percentage",
                "tax_rate_percentage": "7.5",
                "effective_from": "2026-01-01",
                "is_recoverable": "true",
                "is_active": "true",
                "applies_to_sales": "false",
                "applies_to_purchases": "true",
                "tax_collected_account_id": "",
                "tax_paid_account_id": "",
            }
        )
        auth = MagicMock(organization_id=str(existing.organization_id))
        db = MagicMock()

        result = await service.update_tax_code_response(
            request,
            auth,
            str(uuid.uuid4()),
            db,
        )

        assert result == "EDIT_ERROR"
        service.edit_tax_code_form_response.assert_called_once()
        assert (
            service.edit_tax_code_form_response.call_args.kwargs["error"]
            == "Recoverable VAT/GST tax codes that apply to purchases require a tax paid account"
        )


class TestTaxReportPages:
    """Tests for tax report page rendering."""

    @patch("app.services.finance.tax.tax_reports.tax_report_service")
    @patch("app.services.finance.tax.web.get_currency_context", return_value={})
    @patch("app.services.finance.tax.web.base_context", return_value={})
    @patch(
        "app.services.finance.tax.web.templates.TemplateResponse",
        return_value="STAMP_DUTY_REPORT",
    )
    def test_stamp_duty_report_page(
        self,
        mock_template_response,
        _mock_base_context,
        _mock_currency_context,
        mock_report_service,
    ):
        """Stamp duty report page should render the dedicated template."""
        from app.services.finance.tax.tax_reports import StampDutyReportData
        from app.services.finance.tax.web import TaxWebService

        org_id = uuid.uuid4()
        mock_report_service.get_stamp_duty_report.return_value = StampDutyReportData(
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
        )

        service = TaxWebService()
        request = MagicMock()
        auth = MagicMock(organization_id=str(org_id))
        db = MagicMock()

        result = service.stamp_duty_report_page(
            request=request,
            start_date_str="2026-02-01",
            end_date_str="2026-02-28",
            include_details=True,
            auth=auth,
            db=db,
        )

        assert result == "STAMP_DUTY_REPORT"
        mock_report_service.get_stamp_duty_report.assert_called_once()
        assert (
            mock_template_response.call_args.args[1]
            == "finance/reports/stamp_duty_report.html"
        )
