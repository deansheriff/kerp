"""add_fa_maintenance_work_order_part_table

Revision ID: fe8b31b22069
Revises: 20260414_add_inventory_serial_tables
Create Date: 2026-04-15 14:12:34.741926
"""

from alembic import op
from app.alembic_utils import ensure_enum


revision = "fe8b31b22069"
down_revision = "20260414_add_inventory_serial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS fa")

    ensure_enum(
        bind,
        "maintenance_request_status",
        "OPEN",
        "ASSIGNED",
        "IN_PROGRESS",
        "WAITING_FOR_PARTS",
        "COMPLETED",
        "CANCELLED",
    )
    ensure_enum(
        bind,
        "maintenance_priority",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    )
    ensure_enum(
        bind,
        "maintenance_work_order_status",
        "DRAFT",
        "ASSIGNED",
        "IN_PROGRESS",
        "WAITING_FOR_PARTS",
        "COMPLETED",
        "CANCELLED",
    )
    ensure_enum(
        bind,
        "maintenance_work_order_part_status",
        "USED",
        "PENDING_PROCUREMENT",
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fa.maintenance_request (
            maintenance_request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            asset_id UUID NOT NULL,
            request_number VARCHAR(50) NOT NULL,
            title VARCHAR(220) NOT NULL,
            description TEXT,
            priority maintenance_priority NOT NULL DEFAULT 'MEDIUM',
            status maintenance_request_status NOT NULL DEFAULT 'OPEN',
            due_date DATE,
            requested_by_user_id UUID,
            assigned_to_user_id UUID,
            status_changed_at TIMESTAMPTZ,
            status_changed_by_id UUID,
            completed_at TIMESTAMPTZ,
            created_by_user_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_fa_maintenance_request_org_number'
            ) THEN
                ALTER TABLE fa.maintenance_request
                ADD CONSTRAINT uq_fa_maintenance_request_org_number
                UNIQUE (organization_id, request_number);
            END IF;
        END$$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_request_org ON fa.maintenance_request(organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_request_asset ON fa.maintenance_request(asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_request_status ON fa.maintenance_request(organization_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_request_created ON fa.maintenance_request(created_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fa.maintenance_work_order (
            work_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            maintenance_request_id UUID NOT NULL REFERENCES fa.maintenance_request(maintenance_request_id),
            asset_id UUID NOT NULL,
            work_order_number VARCHAR(50) NOT NULL,
            title VARCHAR(220) NOT NULL,
            description TEXT,
            status maintenance_work_order_status NOT NULL DEFAULT 'DRAFT',
            assigned_to_user_id UUID,
            planned_start_date TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            completion_notes TEXT,
            estimated_cost NUMERIC(20,6) NOT NULL DEFAULT 0,
            actual_cost NUMERIC(20,6) NOT NULL DEFAULT 0,
            labor_hours NUMERIC(10,2),
            status_changed_at TIMESTAMPTZ,
            status_changed_by_id UUID,
            created_by_user_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fa_maintenance_work_order_org_number ON fa.maintenance_work_order(organization_id, work_order_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_org ON fa.maintenance_work_order(organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_request ON fa.maintenance_work_order(maintenance_request_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_asset ON fa.maintenance_work_order(asset_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_status ON fa.maintenance_work_order(organization_id, status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fa.maintenance_status_log (
            status_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            entity_type VARCHAR(30) NOT NULL,
            entity_id UUID NOT NULL,
            previous_status VARCHAR(50) NOT NULL,
            new_status VARCHAR(50) NOT NULL,
            changed_by_user_id UUID,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_status_log_org ON fa.maintenance_status_log(organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_status_log_entity ON fa.maintenance_status_log(entity_type, entity_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fa.maintenance_work_order_part (
            maintenance_work_order_part_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES core_org.organization(organization_id),
            work_order_id UUID NOT NULL REFERENCES fa.maintenance_work_order(work_order_id),
            item_id UUID NOT NULL REFERENCES inv.item(item_id),
            warehouse_id UUID REFERENCES inv.warehouse(warehouse_id),
            requested_quantity NUMERIC(20,6) NOT NULL DEFAULT 0,
            issued_quantity NUMERIC(20,6) NOT NULL DEFAULT 0,
            uom VARCHAR(20),
            status maintenance_work_order_part_status NOT NULL DEFAULT 'USED',
            issue_transaction_id UUID REFERENCES inv.inventory_transaction(transaction_id),
            procurement_requisition_id UUID,
            notes TEXT,
            created_by_user_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_part_org ON fa.maintenance_work_order_part(organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_part_wo ON fa.maintenance_work_order_part(work_order_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fa_maintenance_work_order_part_item ON fa.maintenance_work_order_part(item_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fa.maintenance_work_order_part CASCADE")
    op.execute("DROP TABLE IF EXISTS fa.maintenance_status_log CASCADE")
    op.execute("DROP TABLE IF EXISTS fa.maintenance_work_order CASCADE")
    op.execute("DROP TABLE IF EXISTS fa.maintenance_request CASCADE")
    op.execute("DROP TYPE IF EXISTS maintenance_work_order_part_status")
    op.execute("DROP TYPE IF EXISTS maintenance_work_order_status")
    op.execute("DROP TYPE IF EXISTS maintenance_priority")
    op.execute("DROP TYPE IF EXISTS maintenance_request_status")
