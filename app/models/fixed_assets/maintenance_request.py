"""
Fixed Asset Maintenance Request and status history models.
"""

import enum
import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.fixed_assets.maintenance_work_order import MaintenanceWorkOrder


class MaintenanceRequestStatus(str, enum.Enum):
    """Lifecycle states for a maintenance request."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MaintenancePriority(str, enum.Enum):
    """Maintenance urgency options."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MaintenanceRequest(Base):
    """
    Maintenance request raised for an asset repair.
    """

    __tablename__ = "maintenance_request"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "request_number",
            name="uq_fa_maintenance_request_org_number",
        ),
        Index("idx_fa_maintenance_request_org", "organization_id"),
        Index("idx_fa_maintenance_request_asset", "asset_id"),
        Index("idx_fa_maintenance_request_status", "organization_id", "status"),
        Index("idx_fa_maintenance_request_created", "created_at"),
        {"schema": "fa"},
    )

    maintenance_request_id: Mapped[uuid.UUID] = mapped_column(
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
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa.asset.asset_id"),
        nullable=False,
    )

    request_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[MaintenancePriority] = mapped_column(
        SAEnum(MaintenancePriority, name="maintenance_priority"),
        nullable=False,
        default=MaintenancePriority.MEDIUM,
    )
    status: Mapped[MaintenanceRequestStatus] = mapped_column(
        SAEnum(MaintenanceRequestStatus, name="maintenance_request_status"),
        nullable=False,
        default=MaintenanceRequestStatus.OPEN,
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    work_orders: Mapped[list["MaintenanceWorkOrder"]] = relationship(
        "MaintenanceWorkOrder",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="MaintenanceWorkOrder.created_at",
    )

    def __repr__(self) -> str:
        return f"<MaintenanceRequest {self.request_number}: {self.status.value}>"


class MaintenanceStatusLog(Base):
    """
    Generic status change log for maintenance request and work order lifecycle.
    """

    __tablename__ = "maintenance_status_log"
    __table_args__ = (
        Index("idx_fa_maintenance_status_log_org", "organization_id"),
        Index("idx_fa_maintenance_status_log_entity", "entity_type", "entity_id"),
        {"schema": "fa"},
    )

    status_log_id: Mapped[uuid.UUID] = mapped_column(
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
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
