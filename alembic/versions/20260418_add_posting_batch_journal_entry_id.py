"""Add posting_batch.journal_entry_id column to match model.

Model at app/models/finance/gl/posting_batch.py declares this column but the
schema never had it — causing AP posting to fail with UndefinedColumn on the
idempotency-lookup SELECT. AR posting worked only by coincidence (returned
rows before that column was referenced in some paths).
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260418_add_posting_batch_journal_entry_id"
down_revision = "20260416_add_fa_asset_current_depreciation_schedule_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {c["name"] for c in insp.get_columns("posting_batch", schema="gl")}
    if "journal_entry_id" not in columns:
        op.execute(
            """
            ALTER TABLE gl.posting_batch
            ADD COLUMN journal_entry_id UUID
                REFERENCES gl.journal_entry(journal_entry_id)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {c["name"] for c in insp.get_columns("posting_batch", schema="gl")}
    if "journal_entry_id" in columns:
        op.execute("ALTER TABLE gl.posting_batch DROP COLUMN journal_entry_id")
