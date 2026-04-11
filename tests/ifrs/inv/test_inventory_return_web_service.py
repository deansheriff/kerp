from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.models.inventory.inventory_return import InventoryReturnMode
from app.services.inventory.return_web import InventoryReturnWebService


def test_create_return_from_form_manual_success() -> None:
    db = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    source_warehouse_id = uuid.uuid4()
    destination_warehouse_id = uuid.uuid4()

    item = MagicMock()
    item.organization_id = org_id
    item.base_uom = "Nos"
    item.average_cost = Decimal("12")
    item.currency_code = "NGN"
    item.track_lots = False
    item.track_serial_numbers = False

    source_warehouse = MagicMock()
    source_warehouse.organization_id = org_id
    destination_warehouse = MagicMock()
    destination_warehouse.organization_id = org_id
    destination_warehouse.is_receiving = True

    fiscal_period_result = MagicMock()
    fiscal_period = MagicMock()
    fiscal_period.fiscal_period_id = uuid.uuid4()
    fiscal_period_result.first.return_value = fiscal_period

    added_objects: list[object] = []

    def add_capture(obj: object) -> None:
        added_objects.append(obj)

    def flush_assign() -> None:
        for obj in added_objects:
            cast_any: Any = obj
            if getattr(cast_any, "return_id", None) is None:
                cast_any.return_id = uuid.uuid4()

    db.add.side_effect = add_capture
    db.flush.side_effect = flush_assign
    db.get.side_effect = [item, source_warehouse, destination_warehouse]
    db.scalars.side_effect = [fiscal_period_result]

    posted_transaction = MagicMock()
    posted_transaction.transaction_id = uuid.uuid4()

    with patch(
        "app.services.inventory.transaction.InventoryTransactionService.create_transaction",
        return_value=posted_transaction,
    ) as mock_create_transaction:
        inventory_return = InventoryReturnWebService.create_from_form(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            material_request_id=None,
            item_id=str(item_id),
            source_warehouse_id=str(source_warehouse_id),
            destination_warehouse_id=str(destination_warehouse_id),
            quantity="4",
            return_date="2026-04-09",
            reason="Unused items returned from site",
            reference="RTN-001",
            remarks="Manual return",
            lot_number=None,
            serial_numbers_text=None,
        )

    assert inventory_return.return_mode == InventoryReturnMode.MANUAL
    assert inventory_return.item_id == item_id
    assert inventory_return.source_warehouse_id == source_warehouse_id
    assert inventory_return.destination_warehouse_id == destination_warehouse_id
    assert inventory_return.quantity == Decimal("4")
    assert inventory_return.reason == "Unused items returned from site"
    assert inventory_return.posted_transaction_id == posted_transaction.transaction_id
    mock_create_transaction.assert_called_once()


def test_create_return_from_form_material_request_blocks_over_return() -> None:
    db = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    source_warehouse_id = uuid.uuid4()
    destination_warehouse_id = uuid.uuid4()
    material_request_id = uuid.uuid4()
    material_request_item_id = uuid.uuid4()

    item = MagicMock()
    item.organization_id = org_id
    item.base_uom = "Nos"
    item.average_cost = Decimal("12")
    item.currency_code = "NGN"
    item.track_lots = False
    item.track_serial_numbers = False

    source_warehouse = MagicMock()
    source_warehouse.organization_id = org_id
    destination_warehouse = MagicMock()
    destination_warehouse.organization_id = org_id
    destination_warehouse.is_receiving = True

    fiscal_period_result = MagicMock()
    fiscal_period = MagicMock()
    fiscal_period.fiscal_period_id = uuid.uuid4()
    fiscal_period_result.first.return_value = fiscal_period

    material_request_item = MagicMock()
    material_request_item.item_id = material_request_item_id
    material_request_item.inventory_item_id = item_id
    material_request_item.warehouse_id = source_warehouse_id
    material_request_item.requested_qty = Decimal("5")

    material_request = MagicMock()
    material_request.request_id = material_request_id
    material_request.organization_id = org_id
    material_request.default_warehouse_id = None
    material_request.items = [material_request_item]

    material_request_result = MagicMock()
    material_request_result.unique.return_value.first.return_value = material_request

    db.get.side_effect = [item, source_warehouse, destination_warehouse]
    db.scalars.side_effect = [fiscal_period_result, material_request_result]
    db.scalar.return_value = Decimal("4")

    with pytest.raises(ValueError, match="exceeds remaining issued quantity"):
        InventoryReturnWebService.create_from_form(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            material_request_id=str(material_request_id),
            item_id=str(item_id),
            source_warehouse_id=str(source_warehouse_id),
            destination_warehouse_id=str(destination_warehouse_id),
            quantity="2",
            return_date="2026-04-09",
            reason="Return against MR",
            reference=None,
            remarks=None,
            lot_number=None,
            serial_numbers_text=None,
        )


def test_list_context_returns_latest_records() -> None:
    db = MagicMock()
    org_id = uuid.uuid4()

    first_return = MagicMock()
    second_return = MagicMock()

    returns_result = MagicMock()
    returns_result.all.return_value = [first_return, second_return]

    db.scalar.return_value = 2
    db.scalars.return_value = returns_result

    context = InventoryReturnWebService.list_context(
        db=db,
        organization_id=str(org_id),
        page=1,
        limit=50,
    )

    assert context["returns"] == [first_return, second_return]
    assert context["page"] == 1
    assert context["limit"] == 50
    assert context["total_count"] == 2
    assert context["total_pages"] == 1
    db.scalar.assert_called_once()
    db.scalars.assert_called_once()


def test_detail_context_includes_created_by_name() -> None:
    db = MagicMock()
    org_id = uuid.uuid4()

    inventory_return = MagicMock()
    inventory_return.created_by_id = uuid.uuid4()
    inventory_return.updated_by_id = uuid.uuid4()

    scalars_result = MagicMock()
    scalars_result.first.return_value = inventory_return
    db.scalars.return_value = scalars_result
    db.scalar.side_effect = ["Jane Doe", "John Doe"]
    attachment = MagicMock()
    attachment.attachment_id = uuid.uuid4()
    attachment.file_name = "return-image.png"
    attachment.content_type = "image/png"
    attachment.description = "Photo evidence"
    attachment.category.value = "OTHER"
    attachment.file_size = 2048
    attachment.uploaded_at = None

    with patch(
        "app.services.inventory.return_web.attachment_service.list_for_entity",
        return_value=[attachment],
    ):
        context = InventoryReturnWebService.detail_context(
            db=db,
            organization_id=str(org_id),
            return_id=str(uuid.uuid4()),
        )

    assert context["inventory_return"] == inventory_return
    assert context["created_by_name"] == "Jane Doe"
    assert context["updated_by_name"] == "John Doe"
    assert len(context["attachments"]) == 1
    assert context["attachments"][0]["file_name"] == "return-image.png"
    assert context["attachments"][0]["is_image"] is True
    db.scalars.assert_called_once()
    assert db.scalar.call_count == 2
