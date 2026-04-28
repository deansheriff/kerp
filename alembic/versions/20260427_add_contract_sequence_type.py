"""Add CONTRACT to sequence_type enum.

Revision ID: 20260427_add_contract_sequence_type
Revises: 20260427_standardize_asset_numbering
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op

revision = "20260427_add_contract_sequence_type"
down_revision = "20260427_standardize_asset_numbering"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                WHERE enumlabel = 'CONTRACT'
                  AND enumtypid = (
                      SELECT oid FROM pg_type WHERE typname = 'sequence_type'
                  )
            ) THEN
                ALTER TYPE sequence_type ADD VALUE 'CONTRACT';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op.
    pass
