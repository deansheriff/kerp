"""Add mono_account_id column to bank_accounts for Mono Connect integration.

Revision ID: 20260411_add_mono_account_id
Revises: 20260411_outbox_causation_idx
Create Date: 2026-04-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260411_add_mono_account_id"
down_revision = "20260411_outbox_causation_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: check if column exists before adding
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'banking' "
            "AND table_name = 'bank_accounts' "
            "AND column_name = 'mono_account_id'"
        )
    )
    if result.fetchone() is None:
        op.add_column(
            "bank_accounts",
            sa.Column("mono_account_id", sa.String(50), nullable=True),
            schema="banking",
        )
        op.create_index(
            "ix_banking_bank_accounts_mono_account_id",
            "bank_accounts",
            ["mono_account_id"],
            schema="banking",
        )


def downgrade() -> None:
    op.drop_index(
        "ix_banking_bank_accounts_mono_account_id",
        table_name="bank_accounts",
        schema="banking",
    )
    op.drop_column("bank_accounts", "mono_account_id", schema="banking")
