"""add position code and name

Revision ID: 20260513_position_identity
Revises: 20260513_reconcile
Create Date: 2026-05-13 10:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260513_position_identity"
down_revision = "20260513_reconcile"
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

    if not cols:
        return

    if "position_code" not in cols:
        op.add_column(
            "position",
            sa.Column("position_code", sa.String(length=40), nullable=True),
            schema="hr",
        )

    if "position_name" not in cols:
        op.add_column(
            "position",
            sa.Column("position_name", sa.String(length=160), nullable=True),
            schema="hr",
        )

    op.execute("""
        WITH numbered AS (
            SELECT
                p.position_id,
                row_number() OVER (
                    PARTITION BY p.organization_id
                    ORDER BY p.created_at NULLS LAST, p.position_id
                ) AS seq,
                COALESCE(NULLIF(d.designation_name, ''), NULLIF(dep.department_name, ''), 'Position') AS base_name
            FROM hr.position p
            LEFT JOIN hr.designation d ON d.designation_id = p.designation_id
            LEFT JOIN hr.department dep ON dep.department_id = p.department_id
        )
        UPDATE hr.position p
        SET
            position_code = COALESCE(
                NULLIF(p.position_code, ''),
                'POS-' || lpad(numbered.seq::text, 5, '0')
            ),
            position_name = COALESCE(NULLIF(p.position_name, ''), numbered.base_name)
        FROM numbered
        WHERE numbered.position_id = p.position_id
          AND (p.position_code IS NULL OR p.position_code = ''
               OR p.position_name IS NULL OR p.position_name = '')
    """)

    op.alter_column("position", "position_code", nullable=False, schema="hr")
    op.alter_column("position", "position_name", nullable=False, schema="hr")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_position_org_code "
        "ON hr.position(organization_id, position_code)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS hr.uq_hr_position_org_code")
    op.drop_column("position", "position_name", schema="hr")
    op.drop_column("position", "position_code", schema="hr")
