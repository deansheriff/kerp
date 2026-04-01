"""Link expense claims and AP supplier invoices to fleet vehicles.

Revision ID: 20260331_link_vehicle_to_expenses_and_ap_invoices
Revises: 20260331_add_vehicle_to_ap_supplier_invoice
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260331_link_vehicle_to_expenses_and_ap_invoices"
down_revision = "20260331_add_vehicle_to_ap_supplier_invoice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def _fleet_vehicle_has_unique_vehicle_id() -> bool:
        if not inspector.has_table("vehicle", schema="fleet"):
            return False

        pk = inspector.get_pk_constraint("vehicle", schema="fleet") or {}
        pk_cols = [c for c in (pk.get("constrained_columns") or []) if c]
        if pk_cols == ["vehicle_id"]:
            return True

        for uq in inspector.get_unique_constraints("vehicle", schema="fleet") or []:
            uq_cols = [c for c in (uq.get("column_names") or []) if c]
            if uq_cols == ["vehicle_id"]:
                return True

        return False

    # expense.expense_claim: add vehicle_id + FK + composite index
    if inspector.has_table("expense_claim", schema="expense"):
        columns = {
            col["name"]
            for col in inspector.get_columns("expense_claim", schema="expense")
        }
        if "vehicle_id" not in columns:
            op.add_column(
                "expense_claim",
                sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
                schema="expense",
            )

        indexes = {
            idx["name"]
            for idx in inspector.get_indexes("expense_claim", schema="expense")
        }
        if "idx_expense_claim_vehicle" not in indexes:
            op.create_index(
                "idx_expense_claim_vehicle",
                "expense_claim",
                ["organization_id", "vehicle_id"],
                schema="expense",
            )

        if _fleet_vehicle_has_unique_vehicle_id():
            fks = {
                fk["name"]
                for fk in inspector.get_foreign_keys("expense_claim", schema="expense")
                if fk.get("name")
            }
            if "fk_expense_claim_vehicle" not in fks:
                op.create_foreign_key(
                    "fk_expense_claim_vehicle",
                    "expense_claim",
                    "vehicle",
                    ["vehicle_id"],
                    ["vehicle_id"],
                    source_schema="expense",
                    referent_schema="fleet",
                    ondelete="SET NULL",
                )

    # ap.supplier_invoice: add vehicle_id + FK + composite index
    if inspector.has_table("supplier_invoice", schema="ap"):
        columns = {
            col["name"]
            for col in inspector.get_columns("supplier_invoice", schema="ap")
        }
        if "vehicle_id" not in columns:
            op.add_column(
                "supplier_invoice",
                sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
                schema="ap",
            )

        indexes = {
            idx["name"]
            for idx in inspector.get_indexes("supplier_invoice", schema="ap")
        }
        if "idx_supplier_invoice_vehicle" not in indexes:
            op.create_index(
                "idx_supplier_invoice_vehicle",
                "supplier_invoice",
                ["organization_id", "vehicle_id"],
                schema="ap",
            )

        if _fleet_vehicle_has_unique_vehicle_id():
            fks = {
                fk["name"]
                for fk in inspector.get_foreign_keys("supplier_invoice", schema="ap")
                if fk.get("name")
            }
            if "fk_supplier_invoice_vehicle" not in fks:
                op.create_foreign_key(
                    "fk_supplier_invoice_vehicle",
                    "supplier_invoice",
                    "vehicle",
                    ["vehicle_id"],
                    ["vehicle_id"],
                    source_schema="ap",
                    referent_schema="fleet",
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("expense_claim", schema="expense"):
        fks = {
            fk["name"]
            for fk in inspector.get_foreign_keys("expense_claim", schema="expense")
            if fk.get("name")
        }
        if "fk_expense_claim_vehicle" in fks:
            op.drop_constraint(
                "fk_expense_claim_vehicle",
                "expense_claim",
                schema="expense",
                type_="foreignkey",
            )

        indexes = {
            idx["name"]
            for idx in inspector.get_indexes("expense_claim", schema="expense")
        }
        if "idx_expense_claim_vehicle" in indexes:
            op.drop_index(
                "idx_expense_claim_vehicle",
                table_name="expense_claim",
                schema="expense",
            )

        columns = {
            col["name"]
            for col in inspector.get_columns("expense_claim", schema="expense")
        }
        if "vehicle_id" in columns:
            op.drop_column("expense_claim", "vehicle_id", schema="expense")

    if inspector.has_table("supplier_invoice", schema="ap"):
        fks = {
            fk["name"]
            for fk in inspector.get_foreign_keys("supplier_invoice", schema="ap")
            if fk.get("name")
        }
        if "fk_supplier_invoice_vehicle" in fks:
            op.drop_constraint(
                "fk_supplier_invoice_vehicle",
                "supplier_invoice",
                schema="ap",
                type_="foreignkey",
            )

        indexes = {
            idx["name"]
            for idx in inspector.get_indexes("supplier_invoice", schema="ap")
        }
        if "idx_supplier_invoice_vehicle" in indexes:
            op.drop_index(
                "idx_supplier_invoice_vehicle",
                table_name="supplier_invoice",
                schema="ap",
            )

        columns = {
            col["name"]
            for col in inspector.get_columns("supplier_invoice", schema="ap")
        }
        if "vehicle_id" in columns:
            op.drop_column("supplier_invoice", "vehicle_id", schema="ap")
