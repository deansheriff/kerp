"""Succession planning service — business logic for succession plans.

Handles plan CRUD, candidate management, readiness assessments,
and reporting on critical roles and readiness summaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.people.hr.succession import (
    ReadinessLevel,
    SuccessionCandidate,
    SuccessionPlan,
    SuccessionPlanStatus,
)
from app.services.common import PaginatedResult, PaginationParams, paginate

logger = logging.getLogger(__name__)

__all__ = ["SuccessionService"]


# ---------------------------------------------------------------------------
# Input data classes
# ---------------------------------------------------------------------------


@dataclass
class PlanCreateInput:
    """Input for creating a succession plan."""

    position_title: str
    designation_id: UUID | None = None
    department_id: UUID | None = None
    incumbent_id: UUID | None = None
    is_critical_role: bool = False
    risk_of_loss: str = "LOW"
    impact_of_loss: str = "LOW"
    notes: str | None = None
    review_date: date | None = None


@dataclass
class CandidateInput:
    """Input for adding a candidate to a plan."""

    employee_id: UUID
    readiness_level: str = "NOT_READY"
    strengths: str | None = None
    development_areas: str | None = None
    development_actions: dict[str, Any] | None = None
    assessment_date: date | None = None
    assessed_by_id: UUID | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SuccessionService:
    """Service for succession planning operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- helpers --------------------------------------------------------------

    def _get_plan(self, org_id: UUID, plan_id: UUID) -> SuccessionPlan:
        """Fetch a plan or raise ``ValueError``."""
        plan = self.db.scalar(
            select(SuccessionPlan).where(
                SuccessionPlan.plan_id == plan_id,
                SuccessionPlan.organization_id == org_id,
            )
        )
        if not plan:
            raise ValueError(f"Succession plan {plan_id} not found")
        return plan

    def _get_candidate(self, org_id: UUID, candidate_id: UUID) -> SuccessionCandidate:
        """Fetch a candidate or raise ``ValueError``."""
        candidate = self.db.scalar(
            select(SuccessionCandidate).where(
                SuccessionCandidate.candidate_id == candidate_id,
                SuccessionCandidate.organization_id == org_id,
            )
        )
        if not candidate:
            raise ValueError(f"Succession candidate {candidate_id} not found")
        return candidate

    # -- Plan CRUD ------------------------------------------------------------

    def create_plan(
        self,
        org_id: UUID,
        data: PlanCreateInput,
        *,
        created_by_id: UUID | None = None,
    ) -> SuccessionPlan:
        """Create a new succession plan in DRAFT status."""
        plan = SuccessionPlan(
            organization_id=org_id,
            position_title=data.position_title,
            designation_id=data.designation_id,
            department_id=data.department_id,
            incumbent_id=data.incumbent_id,
            is_critical_role=data.is_critical_role,
            risk_of_loss=data.risk_of_loss,
            impact_of_loss=data.impact_of_loss,
            status=SuccessionPlanStatus.DRAFT,
            notes=data.notes,
            review_date=data.review_date,
            created_by_id=created_by_id,
        )
        self.db.add(plan)
        self.db.flush()
        logger.info(
            "Created succession plan %s: %s",
            plan.plan_id,
            plan.position_title,
        )
        return plan

    def activate_plan(self, org_id: UUID, plan_id: UUID) -> SuccessionPlan:
        """Transition a plan from DRAFT to ACTIVE."""
        plan = self._get_plan(org_id, plan_id)
        if plan.status != SuccessionPlanStatus.DRAFT:
            raise ValueError(f"Cannot activate plan in status {plan.status.value}")
        plan.status = SuccessionPlanStatus.ACTIVE
        self.db.flush()
        logger.info("Activated succession plan %s", plan_id)
        return plan

    def get_plan(self, org_id: UUID, plan_id: UUID) -> SuccessionPlan:
        """Get a plan with its candidates eagerly loaded."""
        plan = self.db.scalar(
            select(SuccessionPlan)
            .options(selectinload(SuccessionPlan.candidates))
            .where(
                SuccessionPlan.plan_id == plan_id,
                SuccessionPlan.organization_id == org_id,
            )
        )
        if not plan:
            raise ValueError(f"Succession plan {plan_id} not found")
        return plan

    # -- Candidates -----------------------------------------------------------

    def add_candidate(
        self, org_id: UUID, plan_id: UUID, data: CandidateInput
    ) -> SuccessionCandidate:
        """Add a candidate to an existing plan."""
        # Validate plan exists
        self._get_plan(org_id, plan_id)

        candidate = SuccessionCandidate(
            plan_id=plan_id,
            organization_id=org_id,
            employee_id=data.employee_id,
            readiness_level=data.readiness_level,
            strengths=data.strengths,
            development_areas=data.development_areas,
            development_actions=data.development_actions,
            assessment_date=data.assessment_date,
            assessed_by_id=data.assessed_by_id,
            notes=data.notes,
        )
        self.db.add(candidate)
        self.db.flush()
        logger.info(
            "Added candidate %s to plan %s",
            candidate.candidate_id,
            plan_id,
        )
        return candidate

    def update_candidate_readiness(
        self,
        org_id: UUID,
        candidate_id: UUID,
        readiness_level: str,
        notes: str | None = None,
    ) -> SuccessionCandidate:
        """Update the readiness level (and optional notes) of a candidate."""
        candidate = self._get_candidate(org_id, candidate_id)
        candidate.readiness_level = ReadinessLevel(readiness_level)
        if notes is not None:
            candidate.notes = notes
        self.db.flush()
        logger.info(
            "Updated candidate %s readiness to %s",
            candidate_id,
            readiness_level,
        )
        return candidate

    # -- Listing --------------------------------------------------------------

    def list_plans(
        self,
        org_id: UUID,
        *,
        status: SuccessionPlanStatus | None = None,
        department_id: UUID | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[SuccessionPlan]:
        """List succession plans with optional filters."""
        stmt = (
            select(SuccessionPlan)
            .where(SuccessionPlan.organization_id == org_id)
            .order_by(SuccessionPlan.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(SuccessionPlan.status == status)
        if department_id is not None:
            stmt = stmt.where(SuccessionPlan.department_id == department_id)

        return paginate(self.db, stmt, pagination)

    # -- Reports --------------------------------------------------------------

    def get_critical_roles_without_successors(
        self, org_id: UUID
    ) -> list[SuccessionPlan]:
        """Return active critical-role plans that have zero candidates."""
        # Sub-query: plan_ids that have at least one candidate
        has_candidates = (
            select(SuccessionCandidate.plan_id)
            .where(SuccessionCandidate.organization_id == org_id)
            .distinct()
            .subquery()
        )

        stmt = (
            select(SuccessionPlan)
            .where(
                SuccessionPlan.organization_id == org_id,
                SuccessionPlan.status == SuccessionPlanStatus.ACTIVE,
                SuccessionPlan.is_critical_role.is_(True),
                SuccessionPlan.plan_id.notin_(select(has_candidates.c.plan_id)),
            )
            .order_by(SuccessionPlan.position_title)
        )
        return list(self.db.scalars(stmt).all())

    def get_readiness_summary(self, org_id: UUID) -> dict[str, int]:
        """Return counts of candidates grouped by readiness level."""
        rows = self.db.execute(
            select(
                SuccessionCandidate.readiness_level,
                func.count(SuccessionCandidate.candidate_id),
            )
            .where(SuccessionCandidate.organization_id == org_id)
            .group_by(SuccessionCandidate.readiness_level)
        ).all()

        result: dict[str, int] = {}
        for level, count in rows:
            key = level.value if isinstance(level, ReadinessLevel) else str(level)
            result[key] = count
        return result
