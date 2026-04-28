"""add tax control evidence table

Revision ID: 20260428_add_tax_control_evidence_table
Revises: 20260428_add_employee_final_payroll_fields
Create Date: 2026-04-28 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260428_add_tax_control_evidence_table"
down_revision = "20260428_add_employee_final_payroll_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_evidence",
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("evidence_year", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="MISSING"
        ),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core_org.organization.organization_id"],
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint(
            "organization_id",
            "evidence_year",
            "evidence_type",
            "entity_type",
            "entity_id",
            name="uq_tax_control_evidence_key",
        ),
        schema="tax",
    )
    op.create_index(
        "idx_tax_control_evidence_lookup",
        "control_evidence",
        ["organization_id", "evidence_year", "evidence_type", "entity_type"],
        unique=False,
        schema="tax",
    )
    op.alter_column("control_evidence", "status", server_default=None, schema="tax")


def downgrade() -> None:
    op.drop_index(
        "idx_tax_control_evidence_lookup", table_name="control_evidence", schema="tax"
    )
    op.drop_table("control_evidence", schema="tax")
