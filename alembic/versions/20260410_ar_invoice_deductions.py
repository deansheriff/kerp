"""Add stamp_duty_treatment and vat_withheld to ar.invoice.

Revision ID: 20260410_ar_deductions
Revises: 20260403_add_appraisal_template_pms_config, 20260410_add_inventory_return_updated_by
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260410_ar_deductions"
down_revision = (
    "20260403_add_appraisal_template_pms_config",
    "20260410_add_inventory_return_updated_by",
)
branch_labels = None
depends_on = None

TABLE_NAME = "invoice"
SCHEMA_NAME = "ar"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    columns = {
        column["name"]
        for column in inspector.get_columns(TABLE_NAME, schema=SCHEMA_NAME)
    }

    if "stamp_duty_treatment" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("stamp_duty_treatment", sa.String(20), nullable=True),
            schema=SCHEMA_NAME,
        )

    if "vat_withheld" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "vat_withheld",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    columns = {
        column["name"]
        for column in inspector.get_columns(TABLE_NAME, schema=SCHEMA_NAME)
    }

    if "vat_withheld" in columns:
        op.drop_column(TABLE_NAME, "vat_withheld", schema=SCHEMA_NAME)

    if "stamp_duty_treatment" in columns:
        op.drop_column(TABLE_NAME, "stamp_duty_treatment", schema=SCHEMA_NAME)
