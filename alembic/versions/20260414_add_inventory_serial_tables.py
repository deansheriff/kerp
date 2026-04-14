"""Add inventory serial tracking tables.

Revision ID: 20260414_add_inventory_serial_tables
Revises: 20260411_add_contracts_exit
Create Date: 2026-04-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260414_add_inventory_serial_tables"
down_revision = "20260411_add_contracts_exit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("inventory_serial", schema="inv"):
        op.create_table(
            "inventory_serial",
            sa.Column(
                "serial_id",
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
                "item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.item.item_id"),
                nullable=False,
            ),
            sa.Column("serial_number", sa.String(length=100), nullable=False),
            sa.Column(
                "lot_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.inventory_lot.lot_id"),
                nullable=True,
            ),
            sa.Column(
                "warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse.warehouse_id"),
                nullable=True,
            ),
            sa.Column(
                "location_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse_location.location_id"),
                nullable=True,
            ),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default=sa.text("'AVAILABLE'"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "organization_id",
                "item_id",
                "serial_number",
                name="uq_inventory_serial_item_number",
            ),
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_org",
            "inventory_serial",
            ["organization_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_item",
            "inventory_serial",
            ["item_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_warehouse",
            "inventory_serial",
            ["warehouse_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_lot",
            "inventory_serial",
            ["lot_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_status",
            "inventory_serial",
            ["status"],
            schema="inv",
        )

    if not inspector.has_table("inventory_serial_movement", schema="inv"):
        op.create_table(
            "inventory_serial_movement",
            sa.Column(
                "movement_id",
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
                "serial_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.inventory_serial.serial_id"),
                nullable=False,
            ),
            sa.Column(
                "transaction_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.inventory_transaction.transaction_id"),
                nullable=True,
            ),
            sa.Column("movement_type", sa.String(length=30), nullable=False),
            sa.Column(
                "from_warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse.warehouse_id"),
                nullable=True,
            ),
            sa.Column(
                "to_warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse.warehouse_id"),
                nullable=True,
            ),
            sa.Column(
                "from_location_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse_location.location_id"),
                nullable=True,
            ),
            sa.Column(
                "to_location_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse_location.location_id"),
                nullable=True,
            ),
            sa.Column(
                "lot_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.inventory_lot.lot_id"),
                nullable=True,
            ),
            sa.Column("reason", sa.String(length=100), nullable=True),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_movement_serial",
            "inventory_serial_movement",
            ["serial_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_movement_txn",
            "inventory_serial_movement",
            ["transaction_id"],
            schema="inv",
        )
        op.create_index(
            "idx_inventory_serial_movement_org",
            "inventory_serial_movement",
            ["organization_id"],
            schema="inv",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("inventory_serial_movement", schema="inv"):
        op.drop_index(
            "idx_inventory_serial_movement_org",
            table_name="inventory_serial_movement",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_movement_txn",
            table_name="inventory_serial_movement",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_movement_serial",
            table_name="inventory_serial_movement",
            schema="inv",
        )
        op.drop_table("inventory_serial_movement", schema="inv")

    if inspector.has_table("inventory_serial", schema="inv"):
        op.drop_index(
            "idx_inventory_serial_status",
            table_name="inventory_serial",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_lot",
            table_name="inventory_serial",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_warehouse",
            table_name="inventory_serial",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_item",
            table_name="inventory_serial",
            schema="inv",
        )
        op.drop_index(
            "idx_inventory_serial_org",
            table_name="inventory_serial",
            schema="inv",
        )
        op.drop_table("inventory_serial", schema="inv")
