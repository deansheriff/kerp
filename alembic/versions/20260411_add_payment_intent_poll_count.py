"""Add poll_count and last_poll_error to payments.payment_intent.

Revision ID: 20260411_add_pi_poll_count
Revises: 20260410_ar_deductions
Create Date: 2026-04-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260411_add_pi_poll_count"
down_revision = "20260410_ar_deductions"
branch_labels = None
depends_on = None

TABLE_NAME = "payment_intent"
SCHEMA_NAME = "payments"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    existing = {
        c["name"] for c in inspector.get_columns(TABLE_NAME, schema=SCHEMA_NAME)
    }

    if "poll_count" not in existing:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "poll_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="Number of times this transfer has been polled for status",
            ),
            schema=SCHEMA_NAME,
        )

    if "last_poll_error" not in existing:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "last_poll_error",
                sa.Text(),
                nullable=True,
                comment="Last error message from transfer status polling",
            ),
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    existing = {
        c["name"] for c in inspector.get_columns(TABLE_NAME, schema=SCHEMA_NAME)
    }

    if "last_poll_error" in existing:
        op.drop_column(TABLE_NAME, "last_poll_error", schema=SCHEMA_NAME)

    if "poll_count" in existing:
        op.drop_column(TABLE_NAME, "poll_count", schema=SCHEMA_NAME)
