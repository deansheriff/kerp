"""Asset compliance and audit models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.people.base import AuditMixin, ERPNextSyncMixin


class AssetAuditPlanStatus(str, enum.Enum):
    """Asset audit plan lifecycle."""

    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ADJUSTED = "ADJUSTED"
    CANCELLED = "CANCELLED"


class AssetAuditLineStatus(str, enum.Enum):
    """Audit line verification status."""

    PENDING = "PENDING"
    FOUND = "FOUND"
    MISSING = "MISSING"
    DISCREPANCY = "DISCREPANCY"
    RESOLVED = "RESOLVED"


class AssetAuditAdjustmentType(str, enum.Enum):
    """Adjustment action types for discrepancies."""

    UPDATE_LOCATION = "UPDATE_LOCATION"
    UPDATE_CUSTODIAN = "UPDATE_CUSTODIAN"
    UPDATE_STATUS = "UPDATE_STATUS"
    MARK_FOUND = "MARK_FOUND"
    MARK_MISSING = "MARK_MISSING"


class AssetAuditPlan(Base, AuditMixin, ERPNextSyncMixin):
    """Audit plan header for fixed asset physical verification."""

    __tablename__ = "asset_audit_plan"
    __table_args__ = (
        Index("idx_asset_audit_plan_org", "organization_id"),
        Index("idx_asset_audit_plan_status", "organization_id", "status"),
        Index("idx_asset_audit_plan_date", "planned_date"),
        {"schema": "hr"},
    )

    audit_plan_id: Mapped[uuid.UUID] = mapped_column(
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
    plan_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    scope_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    status: Mapped[AssetAuditPlanStatus] = mapped_column(
        Enum(AssetAuditPlanStatus, name="asset_audit_plan_status", schema="hr"),
        nullable=False,
        default=AssetAuditPlanStatus.DRAFT,
    )
    total_assets: Mapped[int] = mapped_column(nullable=False, default=0)
    found_count: Mapped[int] = mapped_column(nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(nullable=False, default=0)
    discrepancy_count: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class AssetAuditLine(Base, AuditMixin, ERPNextSyncMixin):
    """Asset-level physical check line under an audit plan."""

    __tablename__ = "asset_audit_line"
    __table_args__ = (
        Index("idx_asset_audit_line_plan", "audit_plan_id"),
        Index("idx_asset_audit_line_asset", "organization_id", "asset_id"),
        Index("idx_asset_audit_line_status", "organization_id", "status"),
        {"schema": "hr"},
    )

    audit_line_id: Mapped[uuid.UUID] = mapped_column(
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
    audit_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_audit_plan.audit_plan_id"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expected_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    observed_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expected_custodian_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    observed_custodian_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    expected_status: Mapped[str | None] = mapped_column(String(40))
    observed_status: Mapped[str | None] = mapped_column(String(40))
    physical_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_found: Mapped[bool | None] = mapped_column(nullable=True)
    discrepancy_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AssetAuditLineStatus] = mapped_column(
        Enum(AssetAuditLineStatus, name="asset_audit_line_status", schema="hr"),
        nullable=False,
        default=AssetAuditLineStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class AssetAuditAdjustment(Base, AuditMixin, ERPNextSyncMixin):
    """Adjustment actions performed during audit reconciliation."""

    __tablename__ = "asset_audit_adjustment"
    __table_args__ = (
        Index("idx_asset_audit_adjustment_plan", "audit_plan_id"),
        Index("idx_asset_audit_adjustment_line", "audit_line_id"),
        {"schema": "hr"},
    )

    audit_adjustment_id: Mapped[uuid.UUID] = mapped_column(
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
    audit_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_audit_plan.audit_plan_id"),
        nullable=False,
    )
    audit_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_audit_line.audit_line_id"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    adjustment_type: Mapped[AssetAuditAdjustmentType] = mapped_column(
        Enum(AssetAuditAdjustmentType, name="asset_audit_adjustment_type", schema="hr"),
        nullable=False,
    )
    previous_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    applied_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class AssetAuditDiscrepancy(Base, AuditMixin, ERPNextSyncMixin):
    """Audit discrepancy record created from physical checks."""

    __tablename__ = "asset_audit_discrepancy"
    __table_args__ = (
        Index("idx_asset_audit_discrepancy_plan", "organization_id", "audit_plan_id"),
        Index("idx_asset_audit_discrepancy_line", "organization_id", "audit_line_id"),
        Index("idx_asset_audit_discrepancy_status", "organization_id", "status"),
        {"schema": "hr"},
    )

    discrepancy_id: Mapped[uuid.UUID] = mapped_column(
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
    audit_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_audit_plan.audit_plan_id"),
        nullable=False,
    )
    audit_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.asset_audit_line.audit_line_id"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    discrepancy_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment="OWNERSHIP, LOCATION, STATUS, OTHER",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN",
        server_default=text("'OPEN'"),
    )
    expected_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    observed_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class AssetLifecycleEvent(Base, AuditMixin, ERPNextSyncMixin):
    """Unified audit/compliance trail for asset lifecycle events."""

    __tablename__ = "asset_lifecycle_event"
    __table_args__ = (
        Index("idx_asset_lifecycle_event_asset", "organization_id", "asset_id"),
        Index(
            "idx_asset_lifecycle_event_time",
            "organization_id",
            "asset_id",
            "event_at",
        ),
        Index("idx_asset_lifecycle_event_category", "organization_id", "event_category"),
        Index("idx_asset_lifecycle_event_source", "source_type", "source_record_id"),
        {"schema": "hr"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
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
    event_category: Mapped[str] = mapped_column(String(30), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    new_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    previous_owner_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    new_owner_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )
