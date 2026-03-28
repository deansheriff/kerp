"""Add NYSC dates to hr.employee.

Revision ID: 20260327_add_employee_nysc_dates
Revises: 20260226_add_payroll_entry_employment_type_filter
Create Date: 2026-03-27
"""

import sqlalchemy as sa

from alembic import op

revision = "20260327_add_employee_nysc_dates"
down_revision = "20260226_add_payroll_entry_employment_type_filter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("employee", schema="hr"):
        return

    columns = {col["name"] for col in inspector.get_columns("employee", schema="hr")}

    if "nysc_start_date" not in columns:
        op.add_column(
            "employee",
            sa.Column("nysc_start_date", sa.Date(), nullable=True),
            schema="hr",
        )

    if "nysc_end_date" not in columns:
        op.add_column(
            "employee",
            sa.Column("nysc_end_date", sa.Date(), nullable=True),
            schema="hr",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("employee", schema="hr"):
        return

    columns = {col["name"] for col in inspector.get_columns("employee", schema="hr")}

    if "nysc_end_date" in columns:
        op.drop_column("employee", "nysc_end_date", schema="hr")

    if "nysc_start_date" in columns:
        op.drop_column("employee", "nysc_start_date", schema="hr")
