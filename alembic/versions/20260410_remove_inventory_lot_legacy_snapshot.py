"""Remove legacy inventory lot snapshot columns.

Revision ID: 20260410_remove_inventory_lot_legacy_snapshot
Revises: 20260410_add_inventory_lot_balance_table
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260410_remove_inventory_lot_legacy_snapshot"
down_revision = "20260410_add_inventory_lot_balance_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("inventory_lot", schema="inv")}
    indexes = {index["name"] for index in inspector.get_indexes("inventory_lot", schema="inv")}

    if "idx_lot_warehouse" in indexes:
        op.drop_index("idx_lot_warehouse", table_name="inventory_lot", schema="inv")

    for column_name in [
        "warehouse_id",
        "quantity_on_hand",
        "quantity_allocated",
        "quantity_available",
        "is_quarantined",
        "quarantine_reason",
        "qc_status",
    ]:
        if column_name in columns:
            op.drop_column("inventory_lot", column_name, schema="inv")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("inventory_lot", schema="inv")}

    if "warehouse_id" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column(
                "warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("inv.warehouse.warehouse_id"),
                nullable=True,
            ),
            schema="inv",
        )
    if "quantity_on_hand" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column(
                "quantity_on_hand",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            schema="inv",
        )
    if "quantity_allocated" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column(
                "quantity_allocated",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            schema="inv",
        )
    if "quantity_available" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column(
                "quantity_available",
                sa.Numeric(20, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            schema="inv",
        )
    if "is_quarantined" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column(
                "is_quarantined",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            schema="inv",
        )
    if "quarantine_reason" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column("quarantine_reason", sa.String(length=200), nullable=True),
            schema="inv",
        )
    if "qc_status" not in columns:
        op.add_column(
            "inventory_lot",
            sa.Column("qc_status", sa.String(length=30), nullable=True),
            schema="inv",
        )

    op.execute(
        """
        UPDATE inv.inventory_lot AS lot
        SET
            warehouse_id = agg.warehouse_id,
            quantity_on_hand = agg.quantity_on_hand,
            quantity_allocated = agg.quantity_allocated,
            quantity_available = agg.quantity_available,
            is_quarantined = agg.is_quarantined,
            quarantine_reason = agg.quarantine_reason,
            qc_status = agg.qc_status
        FROM (
            SELECT
                bal.lot_id,
                CASE
                    WHEN COUNT(*) FILTER (
                        WHERE COALESCE(bal.quantity_on_hand, 0) > 0
                           OR COALESCE(bal.quantity_allocated, 0) > 0
                    ) = 1
                    THEN MAX(bal.warehouse_id)
                    ELSE NULL
                END AS warehouse_id,
                COALESCE(SUM(bal.quantity_on_hand), 0) AS quantity_on_hand,
                COALESCE(SUM(bal.quantity_allocated), 0) AS quantity_allocated,
                COALESCE(SUM(bal.quantity_available), 0) AS quantity_available,
                BOOL_OR(COALESCE(bal.is_quarantined, false)) AS is_quarantined,
                MAX(bal.quarantine_reason) FILTER (WHERE bal.quarantine_reason IS NOT NULL) AS quarantine_reason,
                MAX(bal.qc_status) FILTER (WHERE bal.qc_status IS NOT NULL) AS qc_status
            FROM inv.inventory_lot_balance AS bal
            GROUP BY bal.lot_id
        ) AS agg
        WHERE lot.lot_id = agg.lot_id
        """
    )

    op.create_index(
        "idx_lot_warehouse",
        "inventory_lot",
        ["warehouse_id"],
        schema="inv",
    )
