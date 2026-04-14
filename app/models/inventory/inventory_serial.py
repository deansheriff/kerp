"""
Inventory serial number models.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class InventorySerial(Base):
    """One physical serialized unit of inventory."""

    __tablename__ = "inventory_serial"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "item_id",
            "serial_number",
            name="uq_inventory_serial_item_number",
        ),
        Index("idx_inventory_serial_org", "organization_id"),
        Index("idx_inventory_serial_item", "item_id"),
        Index("idx_inventory_serial_warehouse", "warehouse_id"),
        Index("idx_inventory_serial_lot", "lot_id"),
        Index("idx_inventory_serial_status", "status"),
        {"schema": "inv"},
    )

    serial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.item.item_id"),
        nullable=False,
    )
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.inventory_lot.lot_id"),
        nullable=True,
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse.warehouse_id"),
        nullable=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse_location.location_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="AVAILABLE",
        server_default=text("'AVAILABLE'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    movements: Mapped[list["InventorySerialMovement"]] = relationship(
        "InventorySerialMovement",
        foreign_keys="InventorySerialMovement.serial_id",
        lazy="noload",
        back_populates="serial",
    )


class InventorySerialMovement(Base):
    """Audit trail for serial number movements."""

    __tablename__ = "inventory_serial_movement"
    __table_args__ = (
        Index("idx_inventory_serial_movement_serial", "serial_id"),
        Index("idx_inventory_serial_movement_txn", "transaction_id"),
        Index("idx_inventory_serial_movement_org", "organization_id"),
        {"schema": "inv"},
    )

    movement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
    )
    serial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.inventory_serial.serial_id"),
        nullable=False,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.inventory_transaction.transaction_id"),
        nullable=True,
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse.warehouse_id"),
        nullable=True,
    )
    to_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse.warehouse_id"),
        nullable=True,
    )
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse_location.location_id"),
        nullable=True,
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse_location.location_id"),
        nullable=True,
    )
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.inventory_lot.lot_id"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    serial: Mapped[InventorySerial] = relationship(
        "InventorySerial",
        foreign_keys=[serial_id],
        lazy="noload",
        back_populates="movements",
    )
