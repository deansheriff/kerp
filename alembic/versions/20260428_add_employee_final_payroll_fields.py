"""add employee final payroll fields

Revision ID: 20260428_add_employee_final_payroll_fields
Revises: 20260428_mono_sync_daily_schedule
Create Date: 2026-04-28 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_add_employee_final_payroll_fields"
down_revision = "20260428_mono_sync_daily_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee",
        sa.Column(
            "eligible_for_final_payroll",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Allow one final prorated payroll after employee exit",
        ),
        schema="hr",
    )
    op.add_column(
        "employee",
        sa.Column(
            "final_payroll_cutoff_date",
            sa.Date(),
            nullable=True,
            comment="Last date eligible for one-time final payroll after exit",
        ),
        schema="hr",
    )
    op.add_column(
        "employee",
        sa.Column(
            "final_payroll_processed_at",
            sa.DateTime(),
            nullable=True,
            comment="When the final payroll exception was consumed",
        ),
        schema="hr",
    )
    op.alter_column(
        "employee",
        "eligible_for_final_payroll",
        schema="hr",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("employee", "final_payroll_processed_at", schema="hr")
    op.drop_column("employee", "final_payroll_cutoff_date", schema="hr")
    op.drop_column("employee", "eligible_for_final_payroll", schema="hr")
