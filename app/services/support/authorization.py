"""Authorization helpers for support records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.people.hr import Employee, EmployeeStatus
from app.models.support.ticket import Ticket
from app.services.common import coerce_uuid


def employee_id_for_person(
    db: Session,
    organization_id: UUID | str,
    person_id: UUID | str | None,
) -> UUID | None:
    """Resolve the active employee record for an authenticated person."""
    if not person_id:
        return None
    return db.scalar(
        select(Employee.employee_id).where(
            Employee.organization_id == coerce_uuid(organization_id),
            Employee.person_id == coerce_uuid(person_id),
            Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE]),
        )
    )


def can_read_ticket(db: Session, auth, ticket: Ticket) -> bool:
    """Apply all-vs-own ticket scope for a web authentication context."""
    if auth.is_admin or auth.has_permission("support:tickets:read"):
        return True
    if not auth.has_permission("support:tickets:read_own"):
        return False
    employee_id = employee_id_for_person(
        db,
        ticket.organization_id,
        auth.person_id,
    )
    return employee_id is not None and ticket.raised_by_id == employee_id
