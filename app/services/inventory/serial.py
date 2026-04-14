"""
Serial number tracking service.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory.inventory_serial import (
    InventorySerial,
    InventorySerialMovement,
)
from app.models.inventory.inventory_transaction import InventoryTransaction
from app.services.common import coerce_uuid


class InventorySerialService:
    """Manage serialized inventory units and movement history."""

    @staticmethod
    def normalize_serial_numbers(serial_numbers: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in serial_numbers or []:
            serial = str(raw).strip()
            if not serial:
                continue
            key = serial.casefold()
            if key in seen:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate serial number in request: {serial}",
                )
            seen.add(key)
            normalized.append(serial)
        return normalized

    @staticmethod
    def validate_serial_quantity(quantity: Decimal, serial_numbers: list[str]) -> None:
        if quantity != quantity.to_integral_value():
            raise HTTPException(
                status_code=400,
                detail="Serial-tracked quantities must be whole numbers",
            )
        expected = int(quantity)
        if len(serial_numbers) != expected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Serial-tracked quantity requires exactly {expected} serial "
                    f"number(s); received {len(serial_numbers)}"
                ),
            )

    @staticmethod
    def _get_serial(
        db: Session,
        *,
        organization_id: UUID,
        item_id: UUID,
        serial_number: str,
    ) -> InventorySerial | None:
        return db.scalars(
            select(InventorySerial).where(
                InventorySerial.organization_id == organization_id,
                InventorySerial.item_id == item_id,
                InventorySerial.serial_number == serial_number,
            )
        ).first()

    @staticmethod
    def _record_movement(
        db: Session,
        *,
        serial: InventorySerial,
        transaction: InventoryTransaction | None,
        movement_type: str,
        from_warehouse_id: UUID | None = None,
        to_warehouse_id: UUID | None = None,
        from_location_id: UUID | None = None,
        to_location_id: UUID | None = None,
        lot_id: UUID | None = None,
        reason: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> None:
        db.add(
            InventorySerialMovement(
                organization_id=serial.organization_id,
                serial_id=serial.serial_id,
                transaction_id=transaction.transaction_id if transaction else None,
                movement_type=movement_type,
                from_warehouse_id=from_warehouse_id,
                to_warehouse_id=to_warehouse_id,
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                lot_id=lot_id,
                reason=reason,
                created_by_user_id=created_by_user_id,
            )
        )

    @staticmethod
    def receive_serials(
        db: Session,
        *,
        organization_id: UUID,
        item_id: UUID,
        warehouse_id: UUID,
        serial_numbers: list[str],
        transaction: InventoryTransaction | None,
        lot_id: UUID | None = None,
        location_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
        allow_return: bool = False,
    ) -> list[InventorySerial]:
        org_id = coerce_uuid(organization_id)
        itm_id = coerce_uuid(item_id)
        wh_id = coerce_uuid(warehouse_id)
        lot_uuid = coerce_uuid(lot_id) if lot_id else None
        loc_id = coerce_uuid(location_id) if location_id else None
        user_id = coerce_uuid(created_by_user_id) if created_by_user_id else None
        serials = InventorySerialService.normalize_serial_numbers(serial_numbers)
        received: list[InventorySerial] = []

        for serial_number in serials:
            serial = InventorySerialService._get_serial(
                db,
                organization_id=org_id,
                item_id=itm_id,
                serial_number=serial_number,
            )
            if serial and serial.status == "AVAILABLE":
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number already available: {serial_number}",
                )
            if serial and not allow_return:
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number already exists: {serial_number}",
                )
            if not serial:
                serial = InventorySerial(
                    organization_id=org_id,
                    item_id=itm_id,
                    serial_number=serial_number,
                    lot_id=lot_uuid,
                    warehouse_id=wh_id,
                    location_id=loc_id,
                    status="AVAILABLE",
                    is_active=True,
                )
                db.add(serial)
                db.flush()
            else:
                serial.lot_id = lot_uuid or serial.lot_id
                serial.warehouse_id = wh_id
                serial.location_id = loc_id
                serial.status = "AVAILABLE"
                serial.is_active = True

            InventorySerialService._record_movement(
                db,
                serial=serial,
                transaction=transaction,
                movement_type="RETURN" if allow_return else "RECEIPT",
                to_warehouse_id=wh_id,
                to_location_id=loc_id,
                lot_id=serial.lot_id,
                created_by_user_id=user_id,
            )
            received.append(serial)
        return received

    @staticmethod
    def issue_serials(
        db: Session,
        *,
        organization_id: UUID,
        item_id: UUID,
        warehouse_id: UUID,
        serial_numbers: list[str],
        transaction: InventoryTransaction | None,
        lot_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
    ) -> list[InventorySerial]:
        org_id = coerce_uuid(organization_id)
        itm_id = coerce_uuid(item_id)
        wh_id = coerce_uuid(warehouse_id)
        lot_uuid = coerce_uuid(lot_id) if lot_id else None
        user_id = coerce_uuid(created_by_user_id) if created_by_user_id else None
        serials = InventorySerialService.normalize_serial_numbers(serial_numbers)
        issued: list[InventorySerial] = []

        for serial_number in serials:
            serial = InventorySerialService._get_serial(
                db,
                organization_id=org_id,
                item_id=itm_id,
                serial_number=serial_number,
            )
            if not serial:
                raise HTTPException(
                    status_code=404,
                    detail=f"Serial number not found: {serial_number}",
                )
            if serial.status != "AVAILABLE" or serial.warehouse_id != wh_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number is not available in the selected warehouse: {serial_number}",
                )
            if lot_uuid and serial.lot_id != lot_uuid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number does not belong to the selected lot: {serial_number}",
                )

            from_location_id = serial.location_id
            serial.status = "ISSUED"
            serial.warehouse_id = None
            serial.location_id = None

            InventorySerialService._record_movement(
                db,
                serial=serial,
                transaction=transaction,
                movement_type="ISSUE",
                from_warehouse_id=wh_id,
                from_location_id=from_location_id,
                lot_id=serial.lot_id,
                created_by_user_id=user_id,
            )
            issued.append(serial)
        return issued

    @staticmethod
    def transfer_serials(
        db: Session,
        *,
        organization_id: UUID,
        item_id: UUID,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        serial_numbers: list[str],
        issue_transaction: InventoryTransaction | None,
        receipt_transaction: InventoryTransaction | None,
        lot_id: UUID | None = None,
        from_location_id: UUID | None = None,
        to_location_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
    ) -> list[InventorySerial]:
        org_id = coerce_uuid(organization_id)
        itm_id = coerce_uuid(item_id)
        from_wh_id = coerce_uuid(from_warehouse_id)
        to_wh_id = coerce_uuid(to_warehouse_id)
        lot_uuid = coerce_uuid(lot_id) if lot_id else None
        from_loc_id = coerce_uuid(from_location_id) if from_location_id else None
        to_loc_id = coerce_uuid(to_location_id) if to_location_id else None
        user_id = coerce_uuid(created_by_user_id) if created_by_user_id else None
        serials = InventorySerialService.normalize_serial_numbers(serial_numbers)
        transferred: list[InventorySerial] = []

        for serial_number in serials:
            serial = InventorySerialService._get_serial(
                db,
                organization_id=org_id,
                item_id=itm_id,
                serial_number=serial_number,
            )
            if not serial:
                raise HTTPException(
                    status_code=404,
                    detail=f"Serial number not found: {serial_number}",
                )
            if serial.status != "AVAILABLE" or serial.warehouse_id != from_wh_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number is not available in the source warehouse: {serial_number}",
                )
            if lot_uuid and serial.lot_id != lot_uuid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial number does not belong to the selected lot: {serial_number}",
                )

            previous_location_id = from_loc_id or serial.location_id
            InventorySerialService._record_movement(
                db,
                serial=serial,
                transaction=issue_transaction,
                movement_type="TRANSFER_OUT",
                from_warehouse_id=from_wh_id,
                from_location_id=previous_location_id,
                to_warehouse_id=to_wh_id,
                lot_id=serial.lot_id,
                created_by_user_id=user_id,
            )
            serial.warehouse_id = to_wh_id
            serial.location_id = to_loc_id
            serial.status = "AVAILABLE"
            InventorySerialService._record_movement(
                db,
                serial=serial,
                transaction=receipt_transaction,
                movement_type="TRANSFER_IN",
                from_warehouse_id=from_wh_id,
                to_warehouse_id=to_wh_id,
                to_location_id=to_loc_id,
                lot_id=serial.lot_id,
                created_by_user_id=user_id,
            )
            transferred.append(serial)
        return transferred


inventory_serial_service = InventorySerialService()
