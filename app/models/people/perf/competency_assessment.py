"""
CompetencyAssessment Model - Performance Schema.

Records competency ratings within an individual employee appraisal.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.people.hr.job_description import Competency
    from app.models.people.perf.appraisal import Appraisal


class CompetencyAssessment(Base):
    """
    CompetencyAssessment - competency ratings within an appraisal.

    Captures self, manager, and final proficiency ratings for a specific
    competency as part of an individual performance appraisal. Does not
    carry audit (created_by / updated_by) fields — timestamps only.
    """

    __tablename__ = "competency_assessment"
    __table_args__ = (
        Index("idx_comp_assess_appraisal", "appraisal_id"),
        {"schema": "perf"},
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
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
    competency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.competency.competency_id"),
        nullable=False,
    )

    # Flags
    is_priority: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Marked as a priority competency for this appraisal",
    )
    is_development_focus: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Identified as a development focus area",
    )

    # Proficiency targets and ratings
    target_proficiency: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Expected proficiency level (e.g. 1-5)",
    )
    self_rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Employee self-assessed proficiency",
    )
    manager_rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Manager-assessed proficiency",
    )
    final_rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Agreed/calibrated final proficiency",
    )

    # Supporting evidence
    evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Behavioural evidence or examples provided",
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
    competency: Mapped["Competency"] = relationship(
        "Competency",
        foreign_keys=[competency_id],
    )

    def __repr__(self) -> str:
        return (
            f"<CompetencyAssessment appraisal={self.appraisal_id} "
            f"competency={self.competency_id}>"
        )
