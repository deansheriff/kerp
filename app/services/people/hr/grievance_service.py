"""
Grievance Service - Core business logic for employee grievances/complaints.

Handles:
- Grievance submission (including anonymous)
- Workflow transitions: acknowledge, investigate, resolve, close, withdraw
- SLA auto-calculation based on severity
- Paginated listing with filters
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.people.hr.employee import Employee
from app.models.people.hr.grievance import (
    Grievance,
    GrievanceCategory,
    GrievanceSeverity,
    GrievanceStatus,
)
from app.services.common import NotFoundError, ValidationError
from app.services.state_machine import StateMachine

logger = logging.getLogger(__name__)

# SLA days by severity
SLA_DAYS: dict[GrievanceSeverity, int] = {
    GrievanceSeverity.LOW: 14,
    GrievanceSeverity.MEDIUM: 7,
    GrievanceSeverity.HIGH: 3,
    GrievanceSeverity.CRITICAL: 1,
}

# Valid status transitions
VALID_TRANSITIONS: dict[GrievanceStatus, list[GrievanceStatus]] = {
    GrievanceStatus.SUBMITTED: [
        GrievanceStatus.ACKNOWLEDGED,
        GrievanceStatus.WITHDRAWN,
    ],
    GrievanceStatus.ACKNOWLEDGED: [
        GrievanceStatus.INVESTIGATING,
        GrievanceStatus.RESOLVED,
        GrievanceStatus.WITHDRAWN,
    ],
    GrievanceStatus.INVESTIGATING: [
        GrievanceStatus.RESOLVED,
        GrievanceStatus.WITHDRAWN,
    ],
    GrievanceStatus.RESOLVED: [GrievanceStatus.CLOSED],
    GrievanceStatus.CLOSED: [],
    GrievanceStatus.WITHDRAWN: [],
}
_STATE_MACHINE: StateMachine[GrievanceStatus] = StateMachine(VALID_TRANSITIONS)


class GrievanceService:
    """Service for managing employee grievances and complaints."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # Read operations
    # =========================================================================

    def get_grievance(
        self,
        organization_id: UUID,
        grievance_id: UUID,
    ) -> Grievance | None:
        """Get a single grievance by ID, scoped to organization."""
        grievance = self.db.get(Grievance, grievance_id)
        if grievance and grievance.organization_id != organization_id:
            return None
        return grievance

    def get_grievance_or_404(
        self,
        organization_id: UUID,
        grievance_id: UUID,
    ) -> Grievance:
        """Get grievance or raise NotFoundError."""
        grievance = self.get_grievance(organization_id, grievance_id)
        if not grievance:
            raise NotFoundError(f"Grievance {grievance_id} not found")
        return grievance

    def get_grievance_detail(
        self,
        organization_id: UUID,
        grievance_id: UUID,
    ) -> Grievance:
        """Get grievance with relationships eager-loaded."""
        stmt = (
            select(Grievance)
            .options(
                joinedload(Grievance.employee),
                joinedload(Grievance.assigned_to),
                joinedload(Grievance.escalated_to),
            )
            .where(
                Grievance.grievance_id == grievance_id,
                Grievance.organization_id == organization_id,
            )
        )
        grievance = self.db.scalar(stmt)
        if not grievance:
            raise NotFoundError(f"Grievance {grievance_id} not found")
        return grievance

    def list_grievances(
        self,
        organization_id: UUID,
        *,
        status: GrievanceStatus | None = None,
        employee_id: UUID | None = None,
        category: GrievanceCategory | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[Grievance], int]:
        """List grievances with filters and pagination."""
        stmt = select(Grievance).where(
            Grievance.organization_id == organization_id,
        )

        if status is not None:
            stmt = stmt.where(Grievance.status == status)
        if employee_id is not None:
            stmt = stmt.where(Grievance.employee_id == employee_id)
        if category is not None:
            stmt = stmt.where(Grievance.category == category)

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Paginate
        stmt = stmt.order_by(Grievance.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        grievances = list(self.db.scalars(stmt).all())

        return grievances, total

    # =========================================================================
    # Workflow operations
    # =========================================================================

    def submit_grievance(
        self,
        organization_id: UUID,
        *,
        category: GrievanceCategory,
        severity: GrievanceSeverity,
        subject: str,
        description: str,
        is_anonymous: bool = False,
        employee_id: UUID | None = None,
        created_by_id: UUID | None = None,
    ) -> Grievance:
        """Submit a new grievance. Auto-sets SLA based on severity."""
        # Validate employee if provided
        if employee_id is not None:
            employee = self.db.get(Employee, employee_id)
            if not employee:
                raise ValidationError(f"Employee {employee_id} not found")
            if employee.organization_id != organization_id:
                raise ValidationError("Employee does not belong to this organization")

        # Anonymous grievances must not have employee_id
        if is_anonymous:
            employee_id = None

        grievance_number = self._generate_grievance_number(organization_id)
        sla_due = date.today() + timedelta(days=SLA_DAYS[severity])

        grievance = Grievance(
            organization_id=organization_id,
            employee_id=employee_id,
            grievance_number=grievance_number,
            category=category,
            severity=severity,
            subject=subject,
            description=description,
            is_anonymous=is_anonymous,
            status=GrievanceStatus.SUBMITTED,
            sla_due_date=sla_due,
            created_by_id=created_by_id,
        )
        self.db.add(grievance)
        self.db.flush()

        logger.info(
            "Submitted grievance %s (severity=%s, sla=%s)",
            grievance.grievance_number,
            severity.value,
            sla_due,
        )
        return grievance

    def acknowledge_grievance(
        self,
        organization_id: UUID,
        grievance_id: UUID,
        assigned_to_id: UUID,
        *,
        updated_by_id: UUID | None = None,
    ) -> Grievance:
        """Acknowledge a grievance and assign an HR officer."""
        grievance = self.get_grievance_or_404(organization_id, grievance_id)
        _STATE_MACHINE.validate(grievance.status, GrievanceStatus.ACKNOWLEDGED)

        # Validate assigned officer
        officer = self.db.get(Employee, assigned_to_id)
        if not officer:
            raise ValidationError(f"Assigned employee {assigned_to_id} not found")
        if officer.organization_id != organization_id:
            raise ValidationError(
                "Assigned officer does not belong to this organization"
            )

        grievance.status = GrievanceStatus.ACKNOWLEDGED
        grievance.assigned_to_id = assigned_to_id
        grievance.updated_by_id = updated_by_id
        self.db.flush()

        logger.info(
            "Acknowledged grievance %s, assigned to %s",
            grievance.grievance_number,
            assigned_to_id,
        )
        return grievance

    def start_investigation(
        self,
        organization_id: UUID,
        grievance_id: UUID,
        *,
        updated_by_id: UUID | None = None,
    ) -> Grievance:
        """Move grievance to INVESTIGATING status."""
        grievance = self.get_grievance_or_404(organization_id, grievance_id)
        _STATE_MACHINE.validate(grievance.status, GrievanceStatus.INVESTIGATING)

        grievance.status = GrievanceStatus.INVESTIGATING
        grievance.updated_by_id = updated_by_id
        self.db.flush()

        logger.info(
            "Started investigation for grievance %s",
            grievance.grievance_number,
        )
        return grievance

    def resolve_grievance(
        self,
        organization_id: UUID,
        grievance_id: UUID,
        resolution: str,
        *,
        updated_by_id: UUID | None = None,
    ) -> Grievance:
        """Resolve a grievance with a resolution description."""
        grievance = self.get_grievance_or_404(organization_id, grievance_id)
        _STATE_MACHINE.validate(grievance.status, GrievanceStatus.RESOLVED)

        if not resolution.strip():
            raise ValidationError("Resolution text is required")

        grievance.status = GrievanceStatus.RESOLVED
        grievance.resolution = resolution
        grievance.resolution_date = date.today()
        grievance.updated_by_id = updated_by_id
        self.db.flush()

        logger.info(
            "Resolved grievance %s",
            grievance.grievance_number,
        )
        return grievance

    def close_grievance(
        self,
        organization_id: UUID,
        grievance_id: UUID,
        *,
        updated_by_id: UUID | None = None,
    ) -> Grievance:
        """Close a resolved grievance."""
        grievance = self.get_grievance_or_404(organization_id, grievance_id)
        _STATE_MACHINE.validate(grievance.status, GrievanceStatus.CLOSED)

        grievance.status = GrievanceStatus.CLOSED
        grievance.updated_by_id = updated_by_id
        self.db.flush()

        logger.info("Closed grievance %s", grievance.grievance_number)
        return grievance

    def withdraw_grievance(
        self,
        organization_id: UUID,
        grievance_id: UUID,
        *,
        updated_by_id: UUID | None = None,
    ) -> Grievance:
        """Withdraw a grievance (employee-initiated)."""
        grievance = self.get_grievance_or_404(organization_id, grievance_id)
        _STATE_MACHINE.validate(grievance.status, GrievanceStatus.WITHDRAWN)

        grievance.status = GrievanceStatus.WITHDRAWN
        grievance.updated_by_id = updated_by_id
        self.db.flush()

        logger.info("Withdrawn grievance %s", grievance.grievance_number)
        return grievance

    # =========================================================================
    # Helpers
    # =========================================================================

    def _generate_grievance_number(
        self,
        organization_id: UUID,
        max_retries: int = 3,
    ) -> str:
        """Generate a unique grievance number (GRV-YYYY-NNNN)."""
        year = date.today().year
        prefix = f"GRV-{year}-"

        for _attempt in range(max_retries):
            stmt = (
                select(Grievance.grievance_number)
                .where(
                    Grievance.organization_id == organization_id,
                    Grievance.grievance_number.like(f"{prefix}%"),
                )
                .order_by(Grievance.grievance_number.desc())
                .limit(1)
                .with_for_update()
            )
            max_number = self.db.scalar(stmt)

            if max_number:
                try:
                    seq = int(max_number.replace(prefix, "")) + 1
                except (ValueError, TypeError):
                    seq = 1
            else:
                seq = 1

            return f"{prefix}{seq:04d}"

        # Fallback should never be reached
        raise RuntimeError("Failed to generate grievance number")
