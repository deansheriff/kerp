"""
Succession Planning Models - HR Schema.

Models for succession planning: plans and candidates.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.people.base import AuditMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskLevel(str, enum.Enum):
    """Risk-of-loss assessment for a position."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactLevel(str, enum.Enum):
    """Impact-of-loss assessment for a position."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SuccessionPlanStatus(str, enum.Enum):
    """Lifecycle status of a succession plan."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ReadinessLevel(str, enum.Enum):
    """How ready a candidate is to step into the role."""

    READY_NOW = "READY_NOW"
    READY_1_YEAR = "READY_1_YEAR"
    READY_2_YEARS = "READY_2_YEARS"
    DEVELOPMENT_NEEDED = "DEVELOPMENT_NEEDED"
    NOT_READY = "NOT_READY"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SuccessionPlan(Base, AuditMixin):
    """
    Succession plan for a critical or key position.

    Links to the current incumbent (if any) and tracks risk/impact
    assessments.  Candidates are managed via :class:`SuccessionCandidate`.
    """

    __tablename__ = "succession_plan"
    __table_args__ = (
        Index("ix_succession_plan_org_status", "organization_id", "status"),
        {"schema": "hr"},
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
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
    position_title: Mapped[str] = mapped_column(String(200), nullable=False)
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.designation.designation_id"),
        nullable=True,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.department.department_id"),
        nullable=True,
    )
    incumbent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )
    is_critical_role: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    risk_of_loss: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", create_type=False),
        nullable=False,
        default=RiskLevel.LOW,
    )
    impact_of_loss: Mapped[ImpactLevel] = mapped_column(
        Enum(ImpactLevel, name="impact_level", create_type=False),
        nullable=False,
        default=ImpactLevel.LOW,
    )
    status: Mapped[SuccessionPlanStatus] = mapped_column(
        Enum(SuccessionPlanStatus, name="succession_plan_status", create_type=False),
        nullable=False,
        default=SuccessionPlanStatus.DRAFT,
        server_default="DRAFT",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    # Relationships
    candidates: Mapped[list[SuccessionCandidate]] = relationship(
        "SuccessionCandidate",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class SuccessionCandidate(Base):
    """
    A candidate being considered for a succession plan.

    Tracks readiness assessment, strengths, and development actions.
    """

    __tablename__ = "succession_candidate"
    __table_args__ = (
        Index("ix_succession_candidate_plan", "plan_id"),
        Index("ix_succession_candidate_employee", "employee_id"),
        {"schema": "hr"},
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.succession_plan.plan_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=False,
    )
    readiness_level: Mapped[ReadinessLevel] = mapped_column(
        Enum(ReadinessLevel, name="readiness_level", create_type=False),
        nullable=False,
        default=ReadinessLevel.NOT_READY,
    )
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    development_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    development_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assessed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    plan: Mapped[SuccessionPlan] = relationship(
        "SuccessionPlan", back_populates="candidates"
    )
