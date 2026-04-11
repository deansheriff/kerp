"""Add inventory lot balance table.

Revision ID: 20260410_add_inventory_lot_balance_table
Revises: 20260409_add_inventory_return_table
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260410_add_inventory_lot_balance_table"
down_revision = "20260409_add_inventory_return_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("inventory_lot_balance", schema="inv"):
        op.create_table(
            "inventory_lot_balance",
            sa.Column(
                "lot_balance_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "organization_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("core_org.organization.organization_id"),
                nullable=False,
            ),
            sa.Column(
                "lot_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.inventory_lot.lot_id"),
                nullable=False,
            ),
            sa.Column(
                "warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse.warehouse_id"),
                nullable=True,
            ),
            sa.Column(
                "quantity_on_hand",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "quantity_allocated",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "quantity_available",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "is_quarantined",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("quarantine_reason", sa.String(length=200), nullable=True),
            sa.Column("qc_status", sa.String(length=30), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "lot_id",
                "warehouse_id",
                name="uq_inventory_lot_balance",
            ),
            schema="inv",
        )
        op.create_index(
            "idx_lot_balance_org",
            "inventory_lot_balance",
            ["organization_id"],
            schema="inv",
        )
        op.create_index(
            "idx_lot_balance_lot",
            "inventory_lot_balance",
            ["lot_id"],
            schema="inv",
        )
        op.create_index(
            "idx_lot_balance_warehouse",
            "inventory_lot_balance",
            ["warehouse_id"],
            schema="inv",
        )

    op.execute(
        """
        INSERT INTO inv.inventory_lot_balance (
            organization_id,
            lot_id,
            warehouse_id,
            quantity_on_hand,
            quantity_allocated,
            quantity_available,
            is_active,
            is_quarantined,
            quarantine_reason,
            qc_status,
            created_at,
            updated_at
        )
        SELECT
            lot.organization_id,
            lot.lot_id,
            lot.warehouse_id,
            COALESCE(lot.quantity_on_hand, 0),
            COALESCE(lot.quantity_allocated, 0),
            COALESCE(
                lot.quantity_available,
                COALESCE(lot.quantity_on_hand, 0) - COALESCE(lot.quantity_allocated, 0)
            ),
            COALESCE(lot.is_active, true),
            COALESCE(lot.is_quarantined, false),
            lot.quarantine_reason,
            lot.qc_status,
            COALESCE(lot.created_at, now()),
            lot.updated_at
        FROM inv.inventory_lot AS lot
        WHERE NOT EXISTS (
            SELECT 1
            FROM inv.inventory_lot_balance AS bal
            WHERE bal.lot_id = lot.lot_id
              AND (
                    bal.warehouse_id = lot.warehouse_id
                    OR (bal.warehouse_id IS NULL AND lot.warehouse_id IS NULL)
              )
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("inventory_lot_balance", schema="inv"):
        op.drop_index(
            "idx_lot_balance_warehouse",
            table_name="inventory_lot_balance",
            schema="inv",
        )
        op.drop_index(
            "idx_lot_balance_lot",
            table_name="inventory_lot_balance",
            schema="inv",
        )
        op.drop_index(
            "idx_lot_balance_org",
            table_name="inventory_lot_balance",
            schema="inv",
        )
        op.drop_table("inventory_lot_balance", schema="inv")
