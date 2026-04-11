"""
Grievance/Complaint Model - HR Schema.

Tracks employee grievances and complaints through investigation and resolution.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
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
from app.models.people.base import AuditMixin, StatusTrackingMixin

if TYPE_CHECKING:
    from app.models.finance.core_org.organization import Organization
    from app.models.people.hr.employee import Employee


class GrievanceCategory(str, enum.Enum):
    """Categories of grievance/complaint."""

    WORKPLACE = "WORKPLACE"
    HARASSMENT = "HARASSMENT"
    DISCRIMINATION = "DISCRIMINATION"
    POLICY = "POLICY"
    COMPENSATION = "COMPENSATION"
    MANAGEMENT = "MANAGEMENT"
    SAFETY = "SAFETY"
    OTHER = "OTHER"


class GrievanceSeverity(str, enum.Enum):
    """Severity levels for grievances."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GrievanceStatus(str, enum.Enum):
    """Grievance workflow status."""

    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class Grievance(Base, AuditMixin, StatusTrackingMixin):
    """
    Grievance/Complaint Model.

    Tracks employee grievances from submission through investigation,
    resolution, and closure. Supports anonymous submissions.
    """

    __tablename__ = "grievance"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "grievance_number",
            name="uq_grievance_org_number",
        ),
        Index("ix_grievance_org_status", "organization_id", "status"),
        Index("ix_grievance_employee", "employee_id"),
        {"schema": "hr"},
    )

    # Primary key
    grievance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Organization (multi-tenancy)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
    )

    # Employee filing the grievance (nullable for anonymous)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )

    # Grievance identification
    grievance_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Unique grievance reference number per org",
    )

    # Classification
    category: Mapped[GrievanceCategory] = mapped_column(
        Enum(GrievanceCategory, name="grievance_category", schema="hr"),
        nullable=False,
    )
    severity: Mapped[GrievanceSeverity] = mapped_column(
        Enum(GrievanceSeverity, name="grievance_severity", schema="hr"),
        nullable=False,
        default=GrievanceSeverity.MEDIUM,
    )

    # Details
    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Brief summary of the grievance",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of the grievance",
    )

    # Anonymous flag
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the grievance was filed anonymously",
    )

    # Workflow status
    status: Mapped[GrievanceStatus] = mapped_column(
        Enum(GrievanceStatus, name="grievance_status", schema="hr"),
        nullable=False,
        default=GrievanceStatus.SUBMITTED,
    )

    # Assignment
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
        comment="HR officer handling this grievance",
    )

    # Resolution
    resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution details",
    )
    resolution_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date the grievance was resolved",
    )

    # SLA
    sla_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Auto-set SLA deadline based on severity",
    )

    # Escalation
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    escalated_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
        comment="Person the grievance was escalated to",
    )

    # Timestamps
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

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization",
        foreign_keys=[organization_id],
        lazy="select",
    )
    employee: Mapped[Employee | None] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        lazy="select",
    )
    assigned_to: Mapped[Employee | None] = relationship(
        "Employee",
        foreign_keys=[assigned_to_id],
        lazy="select",
    )
    escalated_to: Mapped[Employee | None] = relationship(
        "Employee",
        foreign_keys=[escalated_to_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Grievance {self.grievance_number} [{self.status.value}]>"
