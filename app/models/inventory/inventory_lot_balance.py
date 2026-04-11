"""
Inventory Lot Balance Model - Inventory Schema.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.inventory.inventory_lot import InventoryLot
    from app.models.inventory.warehouse import Warehouse


class InventoryLotBalance(Base):
    """
    Warehouse-scoped stock state for a lot.

    Zero-quantity balances are retained for reporting and historical visibility.
    """

    __tablename__ = "inventory_lot_balance"
    __table_args__ = (
        UniqueConstraint("lot_id", "warehouse_id", name="uq_inventory_lot_balance"),
        Index("idx_lot_balance_org", "organization_id"),
        Index("idx_lot_balance_lot", "lot_id"),
        Index("idx_lot_balance_warehouse", "warehouse_id"),
        {"schema": "inv"},
    )

    lot_balance_id: Mapped[uuid.UUID] = mapped_column(
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
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.inventory_lot.lot_id"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inv.warehouse.warehouse_id"),
        nullable=True,
    )

    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, default=0
    )
    quantity_allocated: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, default=0
    )
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, default=0
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quarantine_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    qc_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

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

    lot: Mapped["InventoryLot"] = relationship(
        "InventoryLot",
        foreign_keys=[lot_id],
        lazy="noload",
        back_populates="balances",
    )
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
        lazy="noload",
    )
