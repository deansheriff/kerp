"""
AppraisalOutcomeAction Model - Performance Schema.

Records concrete actions that result from a completed appraisal, such as
promotions, training enrolments, performance improvement plans, and rewards.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.people.base import AuditMixin
from app.models.people.perf.pms_enums import OutcomeActionStatus, OutcomeActionType

if TYPE_CHECKING:
    from app.models.people.hr.employee import Employee
    from app.models.people.perf.appraisal import Appraisal


class AppraisalOutcomeAction(Base, AuditMixin):
    """
    AppraisalOutcomeAction - action arising from an appraisal outcome.

    Captures the type of action (reward, PIP, training, transfer, etc.),
    who actioned it, when it was actioned, and an optional generic reference
    to a linked entity (e.g. a training programme or transfer record).
    """

    __tablename__ = "appraisal_outcome_action"
    __table_args__ = (
        Index("idx_outcome_appraisal", "appraisal_id"),
        {"schema": "perf"},
    )

    action_id: Mapped[uuid.UUID] = mapped_column(
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

    # Links
    appraisal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("perf.appraisal.appraisal_id"),
        nullable=False,
    )

    # Action classification
    action_type: Mapped[OutcomeActionType] = mapped_column(
        Enum(OutcomeActionType, name="outcome_action_type", schema="perf"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text description of the specific action",
    )

    # Actioning officer
    actioned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )
    actioned_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Generic reference (no FK — points to any linked entity)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of related entity (training programme, transfer record, etc.)",
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Discriminator for reference_id (e.g. 'training_program', 'pip')",
    )

    # Lifecycle status
    status: Mapped[OutcomeActionStatus] = mapped_column(
        Enum(OutcomeActionStatus, name="outcome_action_status", schema="perf"),
        nullable=False,
        default=OutcomeActionStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )

    # Relationships
    appraisal: Mapped["Appraisal"] = relationship(
        "Appraisal",
        foreign_keys=[appraisal_id],
    )
    actioned_by: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[actioned_by_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AppraisalOutcomeAction {self.action_type} appraisal={self.appraisal_id}>"
        )
