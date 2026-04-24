"""
Tests for FixedAssetWebService.
"""

import uuid
from datetime import date, datetime, timezone

try:
    from datetime import UTC  # type: ignore
except ImportError:  # pragma: no cover
    UTC = timezone.utc

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.web.deps import WebAuthContext


class TestFAWebServiceHelpers:
    """Tests for FA web service helper functions."""

    def test_format_date_with_value(self):
        """Test date formatting with valid date."""
        from app.services.fixed_assets.web import _format_date

        result = _format_date(date(2024, 1, 15))
        assert result == "2024-01-15"

    def test_format_date_none(self):
        """Test date formatting with None."""
        from app.services.fixed_assets.web import _format_date

        result = _format_date(None)
        assert result == ""

    def test_format_currency_usd(self):
        """Test currency formatting for USD."""
        from app.services.fixed_assets.web import _format_currency

        result = _format_currency(Decimal("1234.56"), "USD")
        assert result == "USD 1,234.56"

    def test_format_currency_other(self):
        """Test currency formatting for other currencies."""
        from app.services.fixed_assets.web import _format_currency

        result = _format_currency(Decimal("1234.56"), "EUR")
        assert result == "EUR 1,234.56"

    def test_format_currency_none(self):
        """Test currency formatting with None."""
        from app.services.fixed_assets.web import _format_currency

        result = _format_currency(None)
        assert result == ""

    def test_parse_status_valid(self):
        """Test status parsing with valid value."""
        from app.models.fixed_assets.asset import AssetStatus
        from app.services.fixed_assets.web import _parse_status

        result = _parse_status("IN_USE")
        assert result == AssetStatus.IN_USE

    def test_parse_status_lowercase(self):
        """Test status parsing with lowercase value."""
        from app.models.fixed_assets.asset import AssetStatus
        from app.services.fixed_assets.web import _parse_status

        result = _parse_status("in_use")
        assert result == AssetStatus.IN_USE

    def test_parse_status_none(self):
        """Test status parsing with None."""
        from app.services.fixed_assets.web import _parse_status

        result = _parse_status(None)
        assert result is None

    def test_parse_status_invalid(self):
        """Test status parsing with invalid value."""
        from app.services.fixed_assets.web import _parse_status

        result = _parse_status("INVALID_STATUS")
        assert result is None

    def test_try_uuid_valid(self):
        """Test UUID parsing with valid value."""
        from app.services.fixed_assets.web import _try_uuid

        test_uuid = uuid.uuid4()
        result = _try_uuid(str(test_uuid))
        assert result == test_uuid

    def test_try_uuid_none(self):
        """Test UUID parsing with None."""
        from app.services.fixed_assets.web import _try_uuid

        result = _try_uuid(None)
        assert result is None

    def test_try_uuid_invalid(self):
        """Test UUID parsing with invalid value."""
        from app.services.fixed_assets.web import _try_uuid

        result = _try_uuid("not-a-uuid")
        assert result is None


class MockAsset:
    """Mock Asset for testing."""

    def __init__(self, **kwargs):
        from app.models.fixed_assets.asset import AssetStatus

        self.asset_id = kwargs.get("asset_id", uuid.uuid4())
        self.organization_id = kwargs.get("organization_id", uuid.uuid4())
        self.asset_number = kwargs.get("asset_number", "FA-0001")
        self.asset_name = kwargs.get("asset_name", "Office Computer")
        self.category_id = kwargs.get("category_id", uuid.uuid4())
        self.acquisition_date = kwargs.get("acquisition_date", date.today())
        self.acquisition_cost = kwargs.get("acquisition_cost", Decimal("5000.00"))
        self.net_book_value = kwargs.get("net_book_value", Decimal("4000.00"))
        self.currency_code = kwargs.get("currency_code", "USD")
        self.status = kwargs.get("status", AssetStatus.IN_USE)
        self.serial_number = kwargs.get("serial_number")
        self.barcode = kwargs.get("barcode")


class MockAssetCategory:
    """Mock AssetCategory for testing."""

    def __init__(self, **kwargs):
        self.category_id = kwargs.get("category_id", uuid.uuid4())
        self.organization_id = kwargs.get("organization_id", uuid.uuid4())
        self.category_code = kwargs.get("category_code", "EQUIPMENT")
        self.category_name = kwargs.get("category_name", "Office Equipment")
        self.is_active = kwargs.get("is_active", True)


class MockDepreciationRun:
    """Mock DepreciationRun for testing."""

    def __init__(self, **kwargs):
        from app.models.fixed_assets.depreciation_run import DepreciationRunStatus

        self.run_id = kwargs.get("run_id", uuid.uuid4())
        self.organization_id = kwargs.get("organization_id", uuid.uuid4())
        self.run_number = kwargs.get("run_number", "DEP-2024-01")
        self.run_description = kwargs.get("run_description", "January Depreciation")
        self.fiscal_period_id = kwargs.get("fiscal_period_id", uuid.uuid4())
        self.status = kwargs.get("status", DepreciationRunStatus.DRAFT)
        self.assets_processed = kwargs.get("assets_processed", 10)
        self.total_depreciation = kwargs.get("total_depreciation", Decimal("1000.00"))
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


class MockFiscalPeriod:
    """Mock FiscalPeriod for testing."""

    def __init__(self, **kwargs):
        self.fiscal_period_id = kwargs.get("fiscal_period_id", uuid.uuid4())
        self.period_name = kwargs.get("period_name", "January 2024")
        self.start_date = kwargs.get("start_date", date(2024, 1, 1))
        self.end_date = kwargs.get("end_date", date(2024, 1, 31))


class TestFAWebServiceListAssets:
    """Tests for list_assets_context method."""

    def test_list_assets_context_success(self):
        """Test successful assets list context."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_asset = MockAsset(organization_id=org_id)
        mock_category = MockAssetCategory(organization_id=org_id)

        # Mock SA2 patterns: db.scalar() for count, db.execute().all() for rows
        mock_db.scalar.return_value = 1
        mock_db.execute.return_value.all.return_value = [(mock_asset, mock_category)]

        result = FixedAssetWebService.list_assets_context(
            mock_db,
            str(org_id),
            search=None,
            category=None,
            status=None,
            page=1,
        )

        assert "assets" in result
        assert len(result["assets"]) == 1
        assert result["page"] == 1
        assert result["total_count"] == 1

    def test_list_assets_context_with_search(self):
        """Test assets list context with search filter."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.list_assets_context(
            mock_db,
            str(org_id),
            search="computer",
            category=None,
            status=None,
            page=1,
        )

        assert result["search"] == "computer"
        assert result["assets"] == []

    def test_list_assets_context_with_status(self):
        """Test assets list context with status filter."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.list_assets_context(
            mock_db,
            str(org_id),
            search=None,
            category=None,
            status="IN_USE",
            page=1,
        )

        assert result["status"] == "IN_USE"

    def test_list_assets_context_with_category_uuid(self):
        """Test assets list context with category UUID filter."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()
        category_id = uuid.uuid4()

        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.list_assets_context(
            mock_db,
            str(org_id),
            search=None,
            category=str(category_id),
            status=None,
            page=1,
        )

        assert result["category"] == str(category_id)

    def test_list_assets_context_with_category_code(self):
        """Test assets list context with category code filter."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.list_assets_context(
            mock_db,
            str(org_id),
            search=None,
            category="EQUIPMENT",
            status=None,
            page=1,
        )

        assert result["category"] == "EQUIPMENT"


class TestFAWebServiceDepreciation:
    """Tests for depreciation_context method."""

    def test_depreciation_context_success(self):
        """Test successful depreciation context."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_run = MockDepreciationRun(organization_id=org_id)
        mock_period = MockFiscalPeriod()

        mock_db.scalar.return_value = 1
        mock_db.execute.return_value.all.return_value = [(mock_run, mock_period)]

        result = FixedAssetWebService.depreciation_context(
            mock_db,
            str(org_id),
            asset_id=None,
            period=None,
        )

        assert "depreciation_runs" in result
        assert len(result["depreciation_runs"]) == 1
        assert result["total_count"] == 1

    def test_depreciation_context_with_period_filter(self):
        """Test depreciation context with period filter."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()
        period_id = uuid.uuid4()

        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.depreciation_context(
            mock_db,
            str(org_id),
            asset_id=None,
            period=str(period_id),
        )

        assert result["period"] == str(period_id)

    def test_depreciation_context_pagination(self):
        """Test depreciation context pagination."""
        from app.services.fixed_assets.web import FixedAssetWebService

        mock_db = MagicMock()
        org_id = uuid.uuid4()

        mock_db.scalar.return_value = 100
        mock_db.execute.return_value.all.return_value = []

        result = FixedAssetWebService.depreciation_context(
            mock_db,
            str(org_id),
            asset_id=None,
            period=None,
            page=2,
            limit=10,
        )

        assert result["page"] == 2
        assert result["limit"] == 10
        assert result["offset"] == 10
        assert result["total_count"] == 100
        assert result["total_pages"] == 10


class TestFAWebServiceAssetUpdate:
    """Tests for asset update response handling."""

    @pytest.mark.asyncio
    async def test_update_asset_response_filters_pre_use_only_fields_for_in_use_asset(
        self,
    ):
        """In-use assets should ignore pre-use-only form fields and still save."""
        from app.models.fixed_assets.asset import AssetStatus
        from app.services.fixed_assets.web import FixedAssetWebService

        service = FixedAssetWebService()
        org_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        location_id = uuid.uuid4()
        active_asset = MockAsset(
            asset_id=asset_id,
            organization_id=org_id,
            status=AssetStatus.IN_USE,
        )

        mock_db = MagicMock()
        mock_db.get.return_value = active_asset

        request = MagicMock()
        request.form = AsyncMock(
            return_value={
                "asset_name": "Renamed Asset",
                "category_id": str(uuid.uuid4()),
                "serial_number": "SN-200",
                "location_id": str(location_id),
                "description": "Updated description",
                "status": "UNDER_REPAIR",
                "depreciation_schedule_id": "",
                "asset_number": "FA-200",
                "currency_code": "EUR",
                "acquisition_date": "2026-04-01",
                "acquisition_cost": "9000.00",
            }
        )
        auth = WebAuthContext(
            is_authenticated=True,
            organization_id=org_id,
            person_id=uuid.uuid4(),
        )

        with patch("app.services.fixed_assets.web.asset_service.update_asset") as mock_update:
            response = await service.update_asset_response(
                request=request,
                auth=auth,
                db=mock_db,
                asset_id=str(asset_id),
            )

        assert response.status_code == 303
        assert "success=Asset+updated" in response.headers["location"]
        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()

        updates = mock_update.call_args.args[3]
        assert updates == {
            "serial_number": "SN-200",
            "location_id": location_id,
            "description": "Updated description",
            "status": AssetStatus.UNDER_REPAIR,
            "current_depreciation_schedule_id": None,
        }

    @pytest.mark.asyncio
    async def test_update_asset_response_saves_editable_form_fields_for_pre_use_asset(
        self,
    ):
        """Pre-use assets should persist asset number, currency, and schedule."""
        from app.models.fixed_assets.asset import AssetStatus
        from app.services.fixed_assets.web import FixedAssetWebService

        service = FixedAssetWebService()
        org_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        location_id = uuid.uuid4()
        schedule_id = uuid.uuid4()
        asset = MockAsset(
            asset_id=asset_id,
            organization_id=org_id,
            status=AssetStatus.NOT_IN_USE,
        )

        mock_db = MagicMock()
        mock_db.get.return_value = asset

        request = MagicMock()
        request.form = AsyncMock(
            return_value={
                "asset_number": "FA-200",
                "asset_name": "Renamed Asset",
                "category_id": str(uuid.uuid4()),
                "serial_number": "SN-200",
                "location_id": str(location_id),
                "description": "Updated description",
                "status": "IN_STORE",
                "acquisition_date": "2026-04-01",
                "acquisition_cost": "9000.00",
                "currency_code": "EUR",
                "depreciation_schedule_id": str(schedule_id),
            }
        )
        auth = WebAuthContext(
            is_authenticated=True,
            organization_id=org_id,
            person_id=uuid.uuid4(),
        )

        with patch("app.services.fixed_assets.web.asset_service.update_asset") as mock_update:
            response = await service.update_asset_response(
                request=request,
                auth=auth,
                db=mock_db,
                asset_id=str(asset_id),
            )

        assert response.status_code == 303
        updates = mock_update.call_args.args[3]
        assert updates["asset_number"] == "FA-200"
        assert updates["currency_code"] == "EUR"
        assert updates["status"] == AssetStatus.IN_STORE
        assert updates["current_depreciation_schedule_id"] == schedule_id
