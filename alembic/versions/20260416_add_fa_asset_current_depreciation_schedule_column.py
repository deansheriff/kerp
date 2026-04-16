"""Add current_depreciation_schedule_id on fixed assets.

Revision ID: 20260416_add_fa_asset_current_depreciation_schedule_column
Revises: 3644589bb99c
Create Date: 2026-04-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260416_add_fa_asset_current_depreciation_schedule_column"
down_revision = "3644589bb99c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add latest-depreciation-schedule reference on fa.asset."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    asset_columns = {col["name"] for col in inspector.get_columns("asset", schema="fa")} if inspector.has_table("asset", schema="fa") else set()

    if not asset_columns:
        return

    if "current_depreciation_schedule_id" not in asset_columns:
        op.add_column(
            "asset",
            sa.Column(
                "current_depreciation_schedule_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
                comment="Most recent depreciation schedule used for the asset",
            ),
            schema="fa",
        )

        op.create_index(
            "idx_asset_depreciation_schedule",
            "asset",
            ["current_depreciation_schedule_id"],
            schema="fa",
        )



def downgrade() -> None:
    """Revert current depreciation schedule reference."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    asset_columns = {col["name"] for col in inspector.get_columns("asset", schema="fa")} if inspector.has_table("asset", schema="fa") else set()

    if not asset_columns:
        return

    if "current_depreciation_schedule_id" in asset_columns:
        op.drop_index("idx_asset_depreciation_schedule", table_name="asset", schema="fa")
        op.drop_column("asset", "current_depreciation_schedule_id", schema="fa")
