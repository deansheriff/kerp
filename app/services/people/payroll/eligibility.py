"""
Payroll employee eligibility helpers.

Centralizes the employee-status rules for payroll so exited employees can be
paid once more only when explicitly flagged for final payroll.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_

from app.models.people.hr.employee import Employee, EmployeeStatus

FINAL_PAYROLL_EXIT_STATUSES = (
    EmployeeStatus.RESIGNED,
    EmployeeStatus.TERMINATED,
    EmployeeStatus.RETIRED,
)


def payroll_employee_eligibility_clause(
    *,
    period_start: date,
    period_end: date,
):
    """Return a SQLAlchemy clause for employees eligible for payroll."""
    effective_final_payroll_date_in_period = or_(
        and_(
            Employee.final_payroll_cutoff_date.is_(None),
            Employee.date_of_leaving >= period_start,
            Employee.date_of_leaving <= period_end,
        ),
        and_(
            Employee.final_payroll_cutoff_date.is_not(None),
            Employee.final_payroll_cutoff_date >= period_start,
            Employee.final_payroll_cutoff_date <= period_end,
        ),
    )
    return or_(
        Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE]),
        and_(
            Employee.status.in_(FINAL_PAYROLL_EXIT_STATUSES),
            Employee.eligible_for_final_payroll.is_(True),
            Employee.final_payroll_processed_at.is_(None),
            Employee.date_of_leaving.is_not(None),
            Employee.date_of_leaving <= period_end,
            effective_final_payroll_date_in_period,
        ),
    )


def is_employee_payroll_eligible_for_period(
    employee: Employee,
    *,
    period_start: date,
    period_end: date,
) -> bool:
    """Evaluate payroll eligibility in Python for an already-loaded employee."""
    if employee.status in {EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE}:
        return True

    if employee.status not in FINAL_PAYROLL_EXIT_STATUSES:
        return False

    if not employee.eligible_for_final_payroll or employee.final_payroll_processed_at:
        return False

    if employee.date_of_leaving is None:
        return False

    if employee.date_of_leaving > period_end:
        return False

    cutoff = employee.final_payroll_cutoff_date
    effective_date = cutoff or employee.date_of_leaving
    return period_start <= effective_date <= period_end
