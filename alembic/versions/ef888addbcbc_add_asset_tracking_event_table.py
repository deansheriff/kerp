"""add_asset_tracking_event_table

Revision ID: ef888addbcbc
Revises: d43777993180
Create Date: 2026-04-15 14:30:57.906376
"""

from alembic import op
from app.alembic_utils import ensure_enum


revision = "ef888addbcbc"
down_revision = "d43777993180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS hr")

    ensure_enum(
        bind,
        "asset_tracking_method",
        "QR_BARCODE",
        "RFID",
        "GPS",
        schema="hr",
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_tracking_event (
            tracking_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            asset_id UUID NOT NULL,
            tracking_method hr.asset_tracking_method NOT NULL,
            tracking_reference VARCHAR(120),
            tracked_at TIMESTAMPTZ NOT NULL,
            location_id UUID,
            previous_location_id UUID,
            latitude NUMERIC(11,8),
            longitude NUMERIC(11,8),
            accuracy_meters NUMERIC(10,2),
            movement_logged BOOLEAN NOT NULL DEFAULT FALSE,
            scanned_by_user_id UUID,
            notes TEXT,
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
        "CREATE INDEX IF NOT EXISTS idx_asset_tracking_event_asset ON hr.asset_tracking_event(organization_id, asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_tracking_event_method ON hr.asset_tracking_event(organization_id, tracking_method)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_tracking_event_time ON hr.asset_tracking_event(organization_id, tracked_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hr.asset_tracking_event CASCADE")
    op.execute("DROP TYPE IF EXISTS hr.asset_tracking_method")
