"""Authorization helpers for employee-scoped expense records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.people.hr import Employee, EmployeeStatus
from app.services.common import coerce_uuid
from app.services.people.hr.org_resolver import OrgResolver


def current_employee_id(
    db: Session,
    organization_id: UUID | str,
    auth,
) -> UUID | None:
    """Resolve the active employee represented by a web auth context."""
    if auth.employee_id:
        return coerce_uuid(auth.employee_id)
    if not auth.person_id:
        return None
    return db.scalar(
        select(Employee.employee_id).where(
            Employee.organization_id == coerce_uuid(organization_id),
            Employee.person_id == coerce_uuid(auth.person_id),
            Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE]),
        )
    )


def readable_employee_ids(
    db: Session,
    organization_id: UUID | str,
    auth,
    *,
    read_all_permission: str,
    read_own_permission: str,
    read_team_permission: str | None = None,
) -> set[UUID] | None:
    """Return allowed employee IDs, or ``None`` for unrestricted access."""
    if auth.is_admin or auth.has_permission(read_all_permission):
        return None

    employee_id = current_employee_id(db, organization_id, auth)
    if employee_id is None:
        return set()

    allowed: set[UUID] = set()
    if auth.has_permission(read_own_permission):
        allowed.add(employee_id)

    if read_team_permission and auth.has_permission(read_team_permission):
        allowed.add(employee_id)
        reports = OrgResolver(db).get_direct_reports(
            employee_id,
            coerce_uuid(organization_id),
        )
        allowed.update(report.employee_id for report in reports)

    return allowed


def can_read_employee_record(
    db: Session,
    organization_id: UUID | str,
    auth,
    employee_id: UUID | str | None,
    *,
    read_all_permission: str,
    read_own_permission: str,
    read_team_permission: str | None = None,
) -> bool:
    """Check whether an employee-owned record is inside the actor's scope."""
    allowed = readable_employee_ids(
        db,
        organization_id,
        auth,
        read_all_permission=read_all_permission,
        read_own_permission=read_own_permission,
        read_team_permission=read_team_permission,
    )
    return allowed is None or (
        employee_id is not None and coerce_uuid(employee_id) in allowed
    )
