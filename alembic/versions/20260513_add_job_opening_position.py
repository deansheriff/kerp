"""link job openings to positions

Revision ID: 20260513_job_opening_position
Revises: 20260513_position_identity
Create Date: 2026-05-13 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260513_job_opening_position"
down_revision = "20260513_position_identity"
branch_labels = None
depends_on = None


def _columns(inspector, schema: str, table: str) -> set[str]:
    try:
        return {col["name"] for col in inspector.get_columns(table, schema=schema)}
    except Exception:
        return set()


def _index_names(inspector, schema: str, table: str) -> set[str]:
    try:
        return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}
    except Exception:
        return set()


def _fk_names(inspector, schema: str, table: str) -> set[str]:
    try:
        return {
            fk["name"]
            for fk in inspector.get_foreign_keys(table, schema=schema)
            if fk.get("name")
        }
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _columns(inspector, "recruit", "job_opening")
    if not cols:
        return

    if "position_id" not in cols:
        op.add_column(
            "job_opening",
            sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="recruit",
        )

    indexes = _index_names(inspector, "recruit", "job_opening")
    if "ix_recruit_job_opening_position_id" not in indexes:
        op.create_index(
            "ix_recruit_job_opening_position_id",
            "job_opening",
            ["position_id"],
            schema="recruit",
        )

    fks = _fk_names(inspector, "recruit", "job_opening")
    if "fk_job_opening_position_id" not in fks:
        op.create_foreign_key(
            "fk_job_opening_position_id",
            "job_opening",
            "position",
            ["position_id"],
            ["position_id"],
            source_schema="recruit",
            referent_schema="hr",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _columns(inspector, "recruit", "job_opening")
    if "position_id" not in cols:
        return

    fks = _fk_names(inspector, "recruit", "job_opening")
    if "fk_job_opening_position_id" in fks:
        op.drop_constraint(
            "fk_job_opening_position_id",
            "job_opening",
            schema="recruit",
            type_="foreignkey",
        )

    indexes = _index_names(inspector, "recruit", "job_opening")
    if "ix_recruit_job_opening_position_id" in indexes:
        op.drop_index(
            "ix_recruit_job_opening_position_id",
            table_name="job_opening",
            schema="recruit",
        )

    op.drop_column("job_opening", "position_id", schema="recruit")
