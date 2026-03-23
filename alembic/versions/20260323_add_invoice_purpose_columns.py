"""Add invoice purpose columns to AP and AR invoices.

Revision ID: 20260323_add_invoice_purpose_columns
Revises: 20260311_fix_constraints
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260323_add_invoice_purpose_columns"
down_revision = "20260311_fix_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    ap_columns = {
        c["name"] for c in inspector.get_columns("supplier_invoice", schema="ap")
    }
    if "purpose" not in ap_columns:
        op.add_column(
            "supplier_invoice",
            sa.Column(
                "purpose",
                sa.Text(),
                nullable=True,
                comment="Invoice-level purpose/summary separate from line descriptions",
            ),
            schema="ap",
        )

    ar_columns = {c["name"] for c in inspector.get_columns("invoice", schema="ar")}
    if "purpose" not in ar_columns:
        op.add_column(
            "invoice",
            sa.Column(
                "purpose",
                sa.Text(),
                nullable=True,
                comment="Invoice-level purpose/summary separate from line descriptions",
            ),
            schema="ar",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    ar_columns = {c["name"] for c in inspector.get_columns("invoice", schema="ar")}
    if "purpose" in ar_columns:
        op.drop_column("invoice", "purpose", schema="ar")

    ap_columns = {
        c["name"] for c in inspector.get_columns("supplier_invoice", schema="ap")
    }
    if "purpose" in ap_columns:
        op.drop_column("supplier_invoice", "purpose", schema="ap")
