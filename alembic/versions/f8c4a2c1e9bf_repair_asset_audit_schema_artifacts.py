"""Repair missing asset audit/compliance schema artifacts."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "f8c4a2c1e9bf"
down_revision = "3644589bb99c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # Ensure fixed-asset table has a primary key for FK targets.
    fa_asset_pk = insp.get_pk_constraint("asset", schema="fa")
    if not fa_asset_pk or not fa_asset_pk.get("constrained_columns"):
        op.create_primary_key("asset_pkey", "asset", ["asset_id"], schema="fa")

    # Ensure missing audit/lifecycle tables exist.
    hr_tables = set(insp.get_table_names(schema="hr"))
    if "asset_audit_discrepancy" not in hr_tables:
        op.execute(
            """
            CREATE TABLE hr.asset_audit_discrepancy (
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
                updated_at TIMESTAMP WITH TIME ZONE,
                created_by_id UUID,
                updated_by_id UUID,
                erpnext_id VARCHAR(255),
                last_synced_at TIMESTAMPTZ
            );
            """
        )

    if "asset_lifecycle_event" not in hr_tables:
        op.execute(
            """
            CREATE TABLE hr.asset_lifecycle_event (
                event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
                asset_id UUID NOT NULL,
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
                updated_at TIMESTAMP WITH TIME ZONE,
                created_by_id UUID,
                updated_by_id UUID,
                erpnext_id VARCHAR(255),
                last_synced_at TIMESTAMPTZ
            );
            """
        )

    # Add missing indexes for new tables.
    existing_indexes = {idx["name"] for idx in insp.get_indexes("asset_audit_discrepancy", schema="hr")}
    if "idx_asset_audit_discrepancy_plan" not in existing_indexes:
        op.create_index(
            "idx_asset_audit_discrepancy_plan",
            "asset_audit_discrepancy",
            ["organization_id", "audit_plan_id"],
            schema="hr",
        )
    if "idx_asset_audit_discrepancy_line" not in existing_indexes:
        op.create_index(
            "idx_asset_audit_discrepancy_line",
            "asset_audit_discrepancy",
            ["organization_id", "audit_line_id"],
            schema="hr",
        )
    if "idx_asset_audit_discrepancy_status" not in existing_indexes:
        op.create_index(
            "idx_asset_audit_discrepancy_status",
            "asset_audit_discrepancy",
            ["organization_id", "status"],
            schema="hr",
        )

    existing_indexes = {idx["name"] for idx in insp.get_indexes("asset_lifecycle_event", schema="hr")}
    if "idx_asset_lifecycle_event_asset" not in existing_indexes:
        op.create_index(
            "idx_asset_lifecycle_event_asset",
            "asset_lifecycle_event",
            ["organization_id", "asset_id"],
            schema="hr",
        )
    if "idx_asset_lifecycle_event_time" not in existing_indexes:
        op.create_index(
            "idx_asset_lifecycle_event_time",
            "asset_lifecycle_event",
            ["organization_id", "asset_id", "event_at"],
            schema="hr",
        )
    if "idx_asset_lifecycle_event_category" not in existing_indexes:
        op.create_index(
            "idx_asset_lifecycle_event_category",
            "asset_lifecycle_event",
            ["organization_id", "event_category"],
            schema="hr",
        )
    if "idx_asset_lifecycle_event_source" not in existing_indexes:
        op.create_index(
            "idx_asset_lifecycle_event_source",
            "asset_lifecycle_event",
            ["source_type", "source_record_id"],
            schema="hr",
        )

    # Ensure lifecycle event FK points to fixed asset.
    lifecycle_fks = {
        fk["name"] for fk in insp.get_foreign_keys("asset_lifecycle_event", schema="hr")
    }
    if "asset_lifecycle_event_asset_fkey" not in lifecycle_fks:
        op.create_foreign_key(
            "asset_lifecycle_event_asset_fkey",
            "asset_lifecycle_event",
            "asset",
            ["asset_id"],
            ["asset_id"],
            source_schema="hr",
            referent_schema="fa",
        )


def downgrade() -> None:
    op.drop_constraint("asset_lifecycle_event_asset_fkey", "asset_lifecycle_event", type_="foreignkey", schema="hr")
    op.drop_table("asset_lifecycle_event", schema="hr")
    op.drop_table("asset_audit_discrepancy", schema="hr")
    op.drop_constraint("asset_pkey", "asset", type_="primary", schema="fa")
