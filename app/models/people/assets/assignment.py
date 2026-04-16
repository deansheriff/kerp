"""
Asset assignment model for tracking issued assets to employees.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.people.base import AuditMixin, ERPNextSyncMixin


class AssignmentStatus(str, enum.Enum):
    """Status of an asset assignment."""

    ISSUED = "ISSUED"
    RETURNED = "RETURNED"
    TRANSFERRED = "TRANSFERRED"
    LOST = "LOST"


class AssignmentMovementType(str, enum.Enum):
    """Movement event types for assignment lifecycle."""

    ASSIGNED = "ASSIGNED"
    TRANSFERRED = "TRANSFERRED"
    REASSIGNED = "REASSIGNED"
    RETURNED = "RETURNED"
    LOCATION_TRANSFERRED = "LOCATION_TRANSFERRED"


class AssetCondition(str, enum.Enum):
    """Condition of asset at issue/return."""

    NEW = "NEW"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    DAMAGED = "DAMAGED"


class AssetAssignment(Base, AuditMixin, ERPNextSyncMixin):
    """Assignment of a fixed asset to an employee."""

    __tablename__ = "asset_assignment"
    __table_args__ = (
        Index("idx_asset_assignment_asset", "organization_id", "asset_id"),
        Index("idx_asset_assignment_employee", "organization_id", "employee_id"),
        Index("idx_asset_assignment_status", "organization_id", "status"),
        {"schema": "hr"},
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa.asset.asset_id"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=False,
        index=True,
    )
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    returned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="asset_assignment_status"),
        default=AssignmentStatus.ISSUED,
    )
    condition_on_issue: Mapped[AssetCondition | None] = mapped_column(
        Enum(AssetCondition, name="asset_condition"),
        nullable=True,
    )
    condition_on_return: Mapped[AssetCondition | None] = mapped_column(
        Enum(AssetCondition, name="asset_condition"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_from_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_assignment.assignment_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )

    previous_assignment: Mapped[AssetAssignment | None] = relationship(
        "AssetAssignment",
        remote_side="AssetAssignment.assignment_id",
    )


class AssetAssignmentMovement(Base, AuditMixin, ERPNextSyncMixin):
    """Asset assignment/ownership/location movement log."""

    __tablename__ = "asset_assignment_movement"
    __table_args__ = (
        Index("idx_asset_assignment_movement_asset", "organization_id", "asset_id"),
        Index(
            "idx_asset_assignment_movement_employee",
            "organization_id",
            "to_employee_id",
        ),
        Index("idx_asset_assignment_movement_type", "organization_id", "movement_type"),
        {"schema": "hr"},
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
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa.asset.asset_id"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_assignment.assignment_id"),
        nullable=True,
    )
    movement_type: Mapped[AssignmentMovementType] = mapped_column(
        Enum(AssignmentMovementType, name="asset_assignment_movement_type"),
        nullable=False,
    )
    from_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )
    to_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.location.location_id"),
        nullable=True,
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.location.location_id"),
        nullable=True,
    )
    moved_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    moved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )
