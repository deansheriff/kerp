"""
Salary Review Model - HR Schema.

Tracks salary review requests through approval workflow and application.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
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


class ReviewType(str, enum.Enum):
    """Types of salary review."""

    MERIT_INCREASE = "MERIT_INCREASE"
    PROMOTION = "PROMOTION"
    ANNUAL_REVIEW = "ANNUAL_REVIEW"
    MARKET_ADJUSTMENT = "MARKET_ADJUSTMENT"
    PROBATION_CONFIRMATION = "PROBATION_CONFIRMATION"
    DEMOTION = "DEMOTION"


class SalaryReviewStatus(str, enum.Enum):
    """Salary review workflow status."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class SalaryReview(Base, AuditMixin, StatusTrackingMixin):
    """
    Salary Review Model.

    Tracks salary change proposals through draft, approval, and
    application to the employee's salary structure assignment.
    """

    __tablename__ = "salary_review"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_number",
            name="uq_salary_review_org_number",
        ),
        Index("ix_salary_review_org_status", "organization_id", "status"),
        Index("ix_salary_review_employee", "employee_id"),
        {"schema": "hr"},
    )

    # Primary key
    review_id: Mapped[uuid.UUID] = mapped_column(
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

    # Employee under review
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=False,
    )

    # Identification
    review_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Unique review reference number per org",
    )

    # Review classification
    review_type: Mapped[ReviewType] = mapped_column(
        Enum(ReviewType, name="salary_review_type", schema="hr"),
        nullable=False,
    )

    # Salary amounts
    current_salary: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
        comment="Employee current salary at time of review",
    )
    proposed_salary: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
        comment="Proposed new salary",
    )
    approved_salary: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6),
        nullable=True,
        comment="Final approved salary (may differ from proposed)",
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        comment="ISO 4217 currency code",
    )
    percentage_change: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        comment="Percentage change from current to proposed",
    )

    # Effective date
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date the salary change takes effect",
    )

    # Justification
    justification: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason / business case for the salary change",
    )

    # Workflow status
    status: Mapped[SalaryReviewStatus] = mapped_column(
        Enum(SalaryReviewStatus, name="salary_review_status", schema="hr"),
        nullable=False,
        default=SalaryReviewStatus.DRAFT,
    )

    # Link to performance appraisal (optional)
    appraisal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Link to performance appraisal if applicable",
    )

    # Submission
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=True,
    )

    # Approval
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Application
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the salary was actually updated",
    )

    # Rejection
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    employee: Mapped[Employee] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<SalaryReview {self.review_number} [{self.status.value}]>"
