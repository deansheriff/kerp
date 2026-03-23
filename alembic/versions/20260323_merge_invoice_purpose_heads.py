"""Merge invoice purpose migration with existing project sync head.

Revision ID: 20260323_merge_invoice_purpose_heads
Revises: 20260312_add_missing_project_sync_columns, 20260323_add_invoice_purpose_columns
Create Date: 2026-03-23
"""

# revision identifiers, used by Alembic.
revision = "20260323_merge_invoice_purpose_heads"
down_revision = (
    "20260312_add_missing_project_sync_columns",
    "20260323_add_invoice_purpose_columns",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
