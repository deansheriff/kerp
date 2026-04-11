"""Merge inventory-expense and mono-account heads

Revision ID: 20260411_merge_all_heads
Revises: 20260410_merge_inventory_ar_expense_heads, 20260411_add_mono_account_id
Create Date: 2026-04-11 21:21:16.768140

"""

revision = "20260411_merge_all_heads"
down_revision = (
    "20260410_merge_inventory_ar_expense_heads",
    "20260411_add_mono_account_id",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
