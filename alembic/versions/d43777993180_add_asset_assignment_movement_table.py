"""add_asset_assignment_movement_table

Revision ID: d43777993180
Revises: fe8b31b22069
Create Date: 2026-04-15 14:26:06.231004
"""

from alembic import op
from app.alembic_utils import ensure_enum


revision = "d43777993180"
down_revision = "fe8b31b22069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS hr")

    ensure_enum(
        bind,
        "asset_assignment_movement_type",
        "ASSIGNED",
        "TRANSFERRED",
        "REASSIGNED",
        "RETURNED",
        "LOCATION_TRANSFERRED",
        schema="hr",
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_assignment_movement (
            movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            asset_id UUID NOT NULL,
            assignment_id UUID,
            movement_type hr.asset_assignment_movement_type NOT NULL,
            from_employee_id UUID,
            to_employee_id UUID,
            from_location_id UUID,
            to_location_id UUID,
            moved_on DATE NOT NULL,
            notes TEXT,
            moved_by_user_id UUID,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE,
            created_by_id UUID,
            updated_by_id UUID,
            erpnext_id VARCHAR(255),
            last_synced_at TIMESTAMPTZ
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_assignment_movement_asset ON hr.asset_assignment_movement(organization_id, asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_assignment_movement_employee ON hr.asset_assignment_movement(organization_id, to_employee_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_assignment_movement_type ON hr.asset_assignment_movement(organization_id, movement_type)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hr.asset_assignment_movement CASCADE")
    op.execute("DROP TYPE IF EXISTS hr.asset_assignment_movement_type")
