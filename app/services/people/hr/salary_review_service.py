"""
Salary Review Service - Core business logic for salary review workflow.

Handles:
- Review creation and submission
- Approval / rejection workflow
- Applying approved salary to employee's salary structure assignment
- Paginated listing with filters
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.people.hr.employee import Employee
from app.models.people.hr.salary_review import (
    ReviewType,
    SalaryReview,
    SalaryReviewStatus,
)
from app.models.people.payroll.salary_assignment import SalaryStructureAssignment
from app.services.common import NotFoundError, ValidationError
from app.services.state_machine import StateMachine

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS: dict[SalaryReviewStatus, list[SalaryReviewStatus]] = {
    SalaryReviewStatus.DRAFT: [SalaryReviewStatus.SUBMITTED],
    SalaryReviewStatus.SUBMITTED: [
        SalaryReviewStatus.APPROVED,
        SalaryReviewStatus.REJECTED,
    ],
    SalaryReviewStatus.APPROVED: [SalaryReviewStatus.APPLIED],
    SalaryReviewStatus.REJECTED: [SalaryReviewStatus.DRAFT],
    SalaryReviewStatus.APPLIED: [],
}
_STATE_MACHINE: StateMachine[SalaryReviewStatus] = StateMachine(VALID_TRANSITIONS)


def calculate_percentage(current: Decimal, proposed: Decimal) -> Decimal:
    """Calculate percentage change from current to proposed salary."""
    if current == 0:
        return Decimal("0")
    return ((proposed - current) / current * 100).quantize(Decimal("0.0001"))


class SalaryReviewService:
    """Service for managing salary review workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # Read operations
    # =========================================================================

    def get_review(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> SalaryReview | None:
        """Get a single salary review by ID, scoped to organization."""
        review = self.db.get(SalaryReview, review_id)
        if review and review.organization_id != organization_id:
            return None
        return review

    def get_review_or_404(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> SalaryReview:
        """Get salary review or raise NotFoundError."""
        review = self.get_review(organization_id, review_id)
        if not review:
            raise NotFoundError(f"Salary review {review_id} not found")
        return review

    def get_review_detail(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> SalaryReview:
        """Get review with relationships eager-loaded."""
        stmt = (
            select(SalaryReview)
            .options(joinedload(SalaryReview.employee))
            .where(
                SalaryReview.review_id == review_id,
                SalaryReview.organization_id == organization_id,
            )
        )
        review = self.db.scalar(stmt)
        if not review:
            raise NotFoundError(f"Salary review {review_id} not found")
        return review

    def list_reviews(
        self,
        organization_id: UUID,
        *,
        status: SalaryReviewStatus | None = None,
        employee_id: UUID | None = None,
        review_type: ReviewType | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[SalaryReview], int]:
        """List salary reviews with filters and pagination."""
        stmt = select(SalaryReview).where(
            SalaryReview.organization_id == organization_id,
        )

        if status is not None:
            stmt = stmt.where(SalaryReview.status == status)
        if employee_id is not None:
            stmt = stmt.where(SalaryReview.employee_id == employee_id)
        if review_type is not None:
            stmt = stmt.where(SalaryReview.review_type == review_type)

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Paginate
        stmt = stmt.order_by(SalaryReview.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        reviews = list(self.db.scalars(stmt).all())

        return reviews, total

    # =========================================================================
    # Workflow operations
    # =========================================================================

    def create_review(
        self,
        organization_id: UUID,
        *,
        employee_id: UUID,
        review_type: ReviewType,
        current_salary: Decimal,
        proposed_salary: Decimal,
        currency_code: str,
        effective_date: date,
        justification: str,
        appraisal_id: UUID | None = None,
        created_by_id: UUID | None = None,
    ) -> SalaryReview:
        """Create a new salary review in DRAFT status."""
        # Validate employee
        employee = self.db.get(Employee, employee_id)
        if not employee:
            raise ValidationError(f"Employee {employee_id} not found")
        if employee.organization_id != organization_id:
            raise ValidationError("Employee does not belong to this organization")

        percentage = calculate_percentage(current_salary, proposed_salary)
        review_number = self._generate_review_number(organization_id)

        review = SalaryReview(
            organization_id=organization_id,
            employee_id=employee_id,
            review_number=review_number,
            review_type=review_type,
            current_salary=current_salary,
            proposed_salary=proposed_salary,
            currency_code=currency_code,
            percentage_change=percentage,
            effective_date=effective_date,
            justification=justification,
            appraisal_id=appraisal_id,
            status=SalaryReviewStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self.db.add(review)
        self.db.flush()

        logger.info(
            "Created salary review %s for employee %s (%s → %s, %s%%)",
            review.review_number,
            employee_id,
            current_salary,
            proposed_salary,
            percentage,
        )
        return review

    def submit_review(
        self,
        organization_id: UUID,
        review_id: UUID,
        *,
        submitted_by_id: UUID | None = None,
    ) -> SalaryReview:
        """Submit a draft review for approval."""
        review = self.get_review_or_404(organization_id, review_id)
        _STATE_MACHINE.validate(review.status, SalaryReviewStatus.SUBMITTED)

        review.status = SalaryReviewStatus.SUBMITTED
        review.submitted_by_id = submitted_by_id
        review.updated_by_id = submitted_by_id
        self.db.flush()

        logger.info("Submitted salary review %s", review.review_number)
        return review

    def approve_review(
        self,
        organization_id: UUID,
        review_id: UUID,
        approved_by_id: UUID,
        approved_salary: Decimal | None = None,
    ) -> SalaryReview:
        """Approve a submitted salary review."""
        review = self.get_review_or_404(organization_id, review_id)
        _STATE_MACHINE.validate(review.status, SalaryReviewStatus.APPROVED)

        final_salary = (
            approved_salary if approved_salary is not None else review.proposed_salary
        )
        if final_salary <= 0:
            raise ValidationError("Approved salary must be greater than zero")

        review.status = SalaryReviewStatus.APPROVED
        review.approved_salary = final_salary
        review.approved_by_id = approved_by_id
        review.approved_at = datetime.now(timezone.utc)
        review.updated_by_id = approved_by_id

        # Recalculate percentage if approved salary differs from proposed
        if approved_salary is not None:
            review.percentage_change = calculate_percentage(
                review.current_salary, final_salary
            )

        self.db.flush()

        logger.info(
            "Approved salary review %s (approved=%s)",
            review.review_number,
            final_salary,
        )
        return review

    def reject_review(
        self,
        organization_id: UUID,
        review_id: UUID,
        rejected_by_id: UUID,
        reason: str,
    ) -> SalaryReview:
        """Reject a submitted salary review."""
        review = self.get_review_or_404(organization_id, review_id)
        _STATE_MACHINE.validate(review.status, SalaryReviewStatus.REJECTED)

        if not reason.strip():
            raise ValidationError("Rejection reason is required")

        review.status = SalaryReviewStatus.REJECTED
        review.rejection_reason = reason
        review.approved_by_id = rejected_by_id  # track who decided
        review.approved_at = datetime.now(timezone.utc)
        review.updated_by_id = rejected_by_id
        self.db.flush()

        logger.info(
            "Rejected salary review %s: %s",
            review.review_number,
            reason,
        )
        return review

    def apply_review(
        self,
        organization_id: UUID,
        review_id: UUID,
        *,
        applied_by_id: UUID | None = None,
    ) -> SalaryReview:
        """Apply an approved salary review — updates employee's salary assignment."""
        review = self.get_review_or_404(organization_id, review_id)
        _STATE_MACHINE.validate(review.status, SalaryReviewStatus.APPLIED)

        if review.approved_salary is None:
            raise ValidationError("Cannot apply review without an approved salary")

        # Find the employee's current (latest) salary structure assignment
        stmt = (
            select(SalaryStructureAssignment)
            .where(
                SalaryStructureAssignment.organization_id == organization_id,
                SalaryStructureAssignment.employee_id == review.employee_id,
                SalaryStructureAssignment.to_date.is_(None),
            )
            .order_by(SalaryStructureAssignment.from_date.desc())
            .limit(1)
        )
        assignment = self.db.scalar(stmt)

        if assignment:
            # Close the current assignment the day before effective date
            if review.effective_date > assignment.from_date:
                assignment.to_date = review.effective_date - timedelta(days=1)

            # Create new assignment with updated salary
            new_assignment = SalaryStructureAssignment(
                organization_id=organization_id,
                employee_id=review.employee_id,
                structure_id=assignment.structure_id,
                from_date=review.effective_date,
                to_date=None,
                base=review.approved_salary,
                variable=assignment.variable,
                created_by_id=applied_by_id,
            )
            self.db.add(new_assignment)
            logger.info(
                "Created new salary assignment for employee %s: base=%s effective=%s",
                review.employee_id,
                review.approved_salary,
                review.effective_date,
            )
        else:
            logger.warning(
                "No active salary assignment found for employee %s; "
                "review %s applied but salary assignment not updated",
                review.employee_id,
                review.review_number,
            )

        review.status = SalaryReviewStatus.APPLIED
        review.applied_at = datetime.now(timezone.utc)
        review.updated_by_id = applied_by_id
        self.db.flush()

        logger.info("Applied salary review %s", review.review_number)
        return review

    # =========================================================================
    # Helpers
    # =========================================================================

    def _generate_review_number(
        self,
        organization_id: UUID,
        max_retries: int = 3,
    ) -> str:
        """Generate a unique review number (SR-YYYY-NNNN)."""
        year = date.today().year
        prefix = f"SR-{year}-"

        for _attempt in range(max_retries):
            stmt = (
                select(SalaryReview.review_number)
                .where(
                    SalaryReview.organization_id == organization_id,
                    SalaryReview.review_number.like(f"{prefix}%"),
                )
                .order_by(SalaryReview.review_number.desc())
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
        raise RuntimeError("Failed to generate review number")
