"""add_asset_audit_tables

Revision ID: 3644589bb99c
Revises: ef888addbcbc
Create Date: 2026-04-15 14:38:57.500981
"""

from alembic import op
from app.alembic_utils import ensure_enum


revision = "3644589bb99c"
down_revision = "ef888addbcbc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS hr")

    ensure_enum(
        bind,
        "asset_audit_plan_status",
        "DRAFT",
        "IN_PROGRESS",
        "COMPLETED",
        "ADJUSTED",
        "CANCELLED",
        schema="hr",
    )
    ensure_enum(
        bind,
        "asset_audit_line_status",
        "PENDING",
        "FOUND",
        "MISSING",
        "DISCREPANCY",
        "RESOLVED",
        schema="hr",
    )
    ensure_enum(
        bind,
        "asset_audit_adjustment_type",
        "UPDATE_LOCATION",
        "UPDATE_CUSTODIAN",
        "UPDATE_STATUS",
        "MARK_FOUND",
        "MARK_MISSING",
        schema="hr",
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_audit_plan (
            audit_plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            plan_number VARCHAR(50) NOT NULL,
            title VARCHAR(220) NOT NULL,
            planned_date DATE NOT NULL,
            scope_location_id UUID,
            status hr.asset_audit_plan_status NOT NULL DEFAULT 'DRAFT',
            total_assets INTEGER NOT NULL DEFAULT 0,
            found_count INTEGER NOT NULL DEFAULT 0,
            missing_count INTEGER NOT NULL DEFAULT 0,
            discrepancy_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_by_user_id UUID,
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
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_plan_org ON hr.asset_audit_plan(organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_plan_status ON hr.asset_audit_plan(organization_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_plan_date ON hr.asset_audit_plan(planned_date)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_audit_line (
            audit_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            audit_plan_id UUID NOT NULL REFERENCES hr.asset_audit_plan(audit_plan_id),
            asset_id UUID NOT NULL,
            expected_location_id UUID,
            observed_location_id UUID,
            expected_custodian_employee_id UUID,
            observed_custodian_employee_id UUID,
            expected_status VARCHAR(40),
            observed_status VARCHAR(40),
            physical_check_at TIMESTAMPTZ,
            checked_by_user_id UUID,
            is_found BOOLEAN,
            discrepancy_notes TEXT,
            status hr.asset_audit_line_status NOT NULL DEFAULT 'PENDING',
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
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_line_plan ON hr.asset_audit_line(audit_plan_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_line_asset ON hr.asset_audit_line(organization_id, asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_line_status ON hr.asset_audit_line(organization_id, status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_audit_adjustment (
            audit_adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            audit_plan_id UUID NOT NULL REFERENCES hr.asset_audit_plan(audit_plan_id),
            audit_line_id UUID NOT NULL REFERENCES hr.asset_audit_line(audit_line_id),
            asset_id UUID NOT NULL,
            adjustment_type hr.asset_audit_adjustment_type NOT NULL,
            previous_value TEXT,
            new_value TEXT,
            notes TEXT,
            applied_by_user_id UUID,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_adjustment_plan ON hr.asset_audit_adjustment(audit_plan_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_adjustment_line ON hr.asset_audit_adjustment(audit_line_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_audit_discrepancy (
            discrepancy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            audit_plan_id UUID NOT NULL REFERENCES hr.asset_audit_plan(audit_plan_id),
            audit_line_id UUID NOT NULL REFERENCES hr.asset_audit_line(audit_line_id),
            asset_id UUID NOT NULL,
            discrepancy_type VARCHAR(60) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
            expected_state JSONB,
            observed_state JSONB,
            notes TEXT,
            detected_by_user_id UUID,
            detected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            resolved_by_user_id UUID,
            resolution_notes TEXT,
            resolved_at TIMESTAMPTZ,
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
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_discrepancy_plan ON hr.asset_audit_discrepancy(organization_id, audit_plan_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_discrepancy_line ON hr.asset_audit_discrepancy(organization_id, audit_line_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_audit_discrepancy_status ON hr.asset_audit_discrepancy(organization_id, status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr.asset_lifecycle_event (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            asset_id UUID NOT NULL REFERENCES fa.asset(asset_id),
            event_category VARCHAR(30) NOT NULL,
            event_type VARCHAR(80) NOT NULL,
            event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_type VARCHAR(50),
            source_record_id UUID,
            actor_user_id UUID,
            previous_status VARCHAR(40),
            new_status VARCHAR(40),
            previous_location_id UUID,
            new_location_id UUID,
            previous_owner_employee_id UUID,
            new_owner_employee_id UUID,
            notes TEXT,
            event_payload JSONB,
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
        "CREATE INDEX IF NOT EXISTS idx_asset_lifecycle_event_asset ON hr.asset_lifecycle_event(organization_id, asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_lifecycle_event_time ON hr.asset_lifecycle_event(organization_id, asset_id, event_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_lifecycle_event_category ON hr.asset_lifecycle_event(organization_id, event_category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_lifecycle_event_source ON hr.asset_lifecycle_event(source_type, source_record_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hr.asset_lifecycle_event CASCADE")
    op.execute("DROP TABLE IF EXISTS hr.asset_audit_discrepancy CASCADE")
    op.execute("DROP TABLE IF EXISTS hr.asset_audit_adjustment CASCADE")
    op.execute("DROP TABLE IF EXISTS hr.asset_audit_line CASCADE")
    op.execute("DROP TABLE IF EXISTS hr.asset_audit_plan CASCADE")
    op.execute("DROP TYPE IF EXISTS hr.asset_audit_adjustment_type")
    op.execute("DROP TYPE IF EXISTS hr.asset_audit_line_status")
    op.execute("DROP TYPE IF EXISTS hr.asset_audit_plan_status")
