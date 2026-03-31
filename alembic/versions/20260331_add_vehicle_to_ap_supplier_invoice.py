"""Merge heads and restore missing revision in DB.

Revision ID: 20260331_add_vehicle_to_ap_supplier_invoice
Revises: 20260312_add_missing_project_sync_columns, 20260323_add_invoice_purpose_columns, 20260328_pms_create_new_tables
Create Date: 2026-03-31

This revision previously existed in the DB's `alembic_version` table but was missing
from the codebase. It serves as the merge point for the three heads listed above.
"""

revision = "20260331_add_vehicle_to_ap_supplier_invoice"
down_revision = (
    "20260312_add_missing_project_sync_columns",
    "20260323_add_invoice_purpose_columns",
    "20260328_pms_create_new_tables",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

