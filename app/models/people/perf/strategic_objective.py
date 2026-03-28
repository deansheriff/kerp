"""
StrategicObjective Model - Performance Schema.

Organisational strategic objectives linked to appraisal cycles, supporting
hierarchical objective decomposition down to departmental level.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
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
from app.models.people.base import AuditMixin

if TYPE_CHECKING:
    from app.models.people.perf.appraisal_cycle import AppraisalCycle


class StrategicObjective(Base, AuditMixin):
    """
    StrategicObjective - organisational goals linked to an appraisal cycle.

    Supports hierarchical objectives (parent / child) and optional scoping
    to a department. Each objective must have a unique code within the
    organisation.
    """

    __tablename__ = "strategic_objective"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "objective_code",
            name="uq_strategic_obj_code",
        ),
        Index("idx_strat_obj_cycle", "cycle_id"),
        Index("idx_strat_obj_dept", "organization_id", "department_id"),
        {"schema": "perf"},
    )

    objective_id: Mapped[uuid.UUID] = mapped_column(
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

    # Cycle link
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("perf.appraisal_cycle.cycle_id"),
        nullable=False,
    )

    # Optional department scope
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.department.department_id"),
        nullable=True,
    )

    # Self-referential parent link
    parent_objective_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("perf.strategic_objective.objective_id"),
        nullable=True,
    )

    # Identification
    objective_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_document: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Reference document (e.g. state development plan name)",
    )
    target_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Quantitative or qualitative target statement",
    )

    # Weighting and ordering
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Percentage weight of this objective (sum should = 100 per cycle)",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Display ordering within a cycle",
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
    cycle: Mapped["AppraisalCycle"] = relationship(
        "AppraisalCycle",
        foreign_keys=[cycle_id],
    )
    parent_objective: Mapped[Optional["StrategicObjective"]] = relationship(
        "StrategicObjective",
        remote_side=[objective_id],
        foreign_keys=[parent_objective_id],
    )

    def __repr__(self) -> str:
        return f"<StrategicObjective {self.objective_code}>"
