"""Repair missing expense_claim_action constraints and indexes.

Revision ID: 20260410_repair_expense_claim_action_constraints
Revises: 20260403_add_appraisal_template_pms_config, 20260410_add_inventory_lot_balance_table, 20260410_add_inventory_return_updated_by
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260410_repair_expense_claim_action_constraints"
down_revision = (
    "20260403_add_appraisal_template_pms_config",
    "20260410_add_inventory_lot_balance_table",
    "20260410_add_inventory_return_updated_by",
)
branch_labels = None
depends_on = None


TABLE_NAME = "expense_claim_action"
SCHEMA_NAME = "expense"
PK_NAME = "pk_expense_claim_action"
FK_NAME = "fk_expense_claim_action_claim_id_expense_claim"
UQ_NAME = "uq_expense_claim_action"
IDX_NAME = "idx_expense_claim_action_claim"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    pk = inspector.get_pk_constraint(TABLE_NAME, schema=SCHEMA_NAME) or {}
    if not pk.get("constrained_columns"):
        op.create_primary_key(
            PK_NAME,
            TABLE_NAME,
            ["action_id"],
            schema=SCHEMA_NAME,
        )

    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            TABLE_NAME,
            schema=SCHEMA_NAME,
        )
        if constraint.get("name")
    }
    if UQ_NAME not in unique_names:
        op.create_unique_constraint(
            UQ_NAME,
            TABLE_NAME,
            ["organization_id", "claim_id", "action_type"],
            schema=SCHEMA_NAME,
        )

    claim_pk = inspector.get_pk_constraint("expense_claim", schema=SCHEMA_NAME) or {}
    claim_unique_sets = {
        tuple(constraint.get("column_names") or [])
        for constraint in inspector.get_unique_constraints(
            "expense_claim",
            schema=SCHEMA_NAME,
        )
    }
    claim_id_is_keyed = claim_pk.get("constrained_columns") == ["claim_id"] or (
        "claim_id",
    ) in claim_unique_sets

    foreign_key_names = {
        fk["name"]
        for fk in inspector.get_foreign_keys(TABLE_NAME, schema=SCHEMA_NAME)
        if fk.get("name")
    }
    if FK_NAME not in foreign_key_names and claim_id_is_keyed:
        op.create_foreign_key(
            FK_NAME,
            TABLE_NAME,
            "expense_claim",
            ["claim_id"],
            ["claim_id"],
            source_schema=SCHEMA_NAME,
            referent_schema=SCHEMA_NAME,
        )

    index_names = {
        index["name"]
        for index in inspector.get_indexes(TABLE_NAME, schema=SCHEMA_NAME)
        if index.get("name")
    }
    if IDX_NAME not in index_names:
        op.create_index(
            IDX_NAME,
            TABLE_NAME,
            ["claim_id"],
            unique=False,
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    index_names = {
        index["name"]
        for index in inspector.get_indexes(TABLE_NAME, schema=SCHEMA_NAME)
        if index.get("name")
    }
    if IDX_NAME in index_names:
        op.drop_index(IDX_NAME, table_name=TABLE_NAME, schema=SCHEMA_NAME)

    foreign_key_names = {
        fk["name"]
        for fk in inspector.get_foreign_keys(TABLE_NAME, schema=SCHEMA_NAME)
        if fk.get("name")
    }
    if FK_NAME in foreign_key_names:
        op.drop_constraint(FK_NAME, TABLE_NAME, schema=SCHEMA_NAME, type_="foreignkey")

    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            TABLE_NAME,
            schema=SCHEMA_NAME,
        )
        if constraint.get("name")
    }
    if UQ_NAME in unique_names:
        op.drop_constraint(UQ_NAME, TABLE_NAME, schema=SCHEMA_NAME, type_="unique")

    pk = inspector.get_pk_constraint(TABLE_NAME, schema=SCHEMA_NAME) or {}
    if pk.get("name") == PK_NAME:
        op.drop_constraint(PK_NAME, TABLE_NAME, schema=SCHEMA_NAME, type_="primary")
