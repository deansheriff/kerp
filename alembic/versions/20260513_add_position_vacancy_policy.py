"""add position vacancy routing policy

Revision ID: 20260513_position_vacancy_policy
Revises: 20260513_job_opening_position
Create Date: 2026-05-13 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260513_position_vacancy_policy"
down_revision = "20260513_job_opening_position"
branch_labels = None
depends_on = None


def _columns(inspector, schema: str, table: str) -> set[str]:
    try:
        return {col["name"] for col in inspector.get_columns(table, schema=schema)}
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _columns(inspector, "hr", "position")
    if not cols or "vacancy_routing_policy" in cols:
        return

    op.add_column(
        "position",
        sa.Column(
            "vacancy_routing_policy",
            sa.String(length=32),
            nullable=False,
            server_default="SKIP_UP",
        ),
        schema="hr",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _columns(inspector, "hr", "position")
    if "vacancy_routing_policy" in cols:
        op.drop_column("position", "vacancy_routing_policy", schema="hr")
