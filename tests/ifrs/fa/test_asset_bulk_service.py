import uuid
from unittest.mock import MagicMock

from app.models.fixed_assets.asset import AssetStatus
from app.services.fixed_assets.bulk import AssetBulkService


def test_cannot_delete_asset_with_lifecycle_history(mock_db, org_id):
    asset = MagicMock()
    asset.asset_id = uuid.uuid4()
    asset.asset_name = "DT-AST-0555"
    asset.status = AssetStatus.NOT_IN_USE

    mock_db.scalar.side_effect = [0, 3]

    service = AssetBulkService(mock_db, org_id)

    can_delete, reason = service.can_delete(asset)

    assert can_delete is False
    assert "lifecycle history" in reason
    assert "DT-AST-0555" in reason


def test_can_delete_asset_without_depreciation_or_lifecycle_history(mock_db, org_id):
    asset = MagicMock()
    asset.asset_id = uuid.uuid4()
    asset.asset_name = "DT-AST-0556"
    asset.status = AssetStatus.NOT_IN_USE

    mock_db.scalar.side_effect = [0, 0]

    service = AssetBulkService(mock_db, org_id)

    can_delete, reason = service.can_delete(asset)

    assert can_delete is True
    assert reason == ""
