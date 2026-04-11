"""Merge April 10 inventory, AR, and expense heads.

Revision ID: 20260410_merge_inventory_ar_expense_heads
Revises: 20260410_ar_deductions, 20260410_remove_inventory_lot_legacy_snapshot, 20260410_repair_expense_claim_action_constraints
Create Date: 2026-04-10
"""

revision = "20260410_merge_inventory_ar_expense_heads"
down_revision = (
    "20260410_ar_deductions",
    "20260410_remove_inventory_lot_legacy_snapshot",
    "20260410_repair_expense_claim_action_constraints",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
