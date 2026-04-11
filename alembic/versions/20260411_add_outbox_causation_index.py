"""Add index on event_outbox.causation_id to prevent lock contention.

Revision ID: 20260411_outbox_causation_idx
Revises: 20260411_add_pi_poll_count
Create Date: 2026-04-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260411_outbox_causation_idx"
down_revision = "20260411_add_pi_poll_count"
branch_labels = None
depends_on = None

TABLE_NAME = "event_outbox"
SCHEMA_NAME = "platform"
INDEX_NAME = "idx_outbox_causation"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes(TABLE_NAME, schema=SCHEMA_NAME)
    }
    if INDEX_NAME not in existing_indexes:
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            ["causation_id"],
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME, schema=SCHEMA_NAME):
        return

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes(TABLE_NAME, schema=SCHEMA_NAME)
    }
    if INDEX_NAME in existing_indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME, schema=SCHEMA_NAME)
