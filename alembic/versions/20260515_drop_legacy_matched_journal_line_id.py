"""Drop legacy banking.bank_statement_lines.matched_journal_line_id.

After stages 1 and 2 of the legacy-column migration:
- All readers go through the BankStatementLineMatch junction (the canonical
  source) with a now-obsolete legacy-column fallback.
- All writers have stopped populating the column (reconciliation_parts/
  matching.py lines 158/1409/1470/1474/1523).
- Existing matches in the DB still have the legacy column set, but the
  junction is dual-populated by the 2026-02-14 backfill and the
  2026-05-15 Splynx backfill.

This migration drops the column.  It is irreversible in the sense that the
downgrade re-adds the column but with NULL data (data not restored from
junction).  A true revert would need a backfill-from-junction migration.

Pre-flight (run before deploying this migration):
    -- Every matched line should be in the junction now:
    SELECT COUNT(*)
    FROM banking.bank_statement_lines bsl
    LEFT JOIN banking.bank_statement_line_matches m
      ON m.statement_line_id = bsl.line_id
    WHERE bsl.is_matched = TRUE
      AND m.match_id IS NULL;
    -- Expect 0.  Any non-zero result means there are matched lines that
    -- depend on the legacy column and would lose their journal link.

Revision ID: 20260515_drop_legacy_matched_jl_id
Revises: 20260515_backfill_splynx_match_junction
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260515_drop_legacy_matched_jl_id"
down_revision: str | None = "20260515_backfill_splynx_match_junction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str, schema: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    if _column_exists("bank_statement_lines", "matched_journal_line_id", "banking"):
        op.drop_column(
            "bank_statement_lines",
            "matched_journal_line_id",
            schema="banking",
        )


def downgrade() -> None:
    """Re-add the column as nullable.

    Data is NOT restored from the junction — anyone wanting full revert
    needs a follow-up migration that backfills the column from
    ``bank_statement_line_matches`` (junction primary rows).
    """
    if _column_exists("bank_statement_lines", "matched_journal_line_id", "banking"):
        return
    op.add_column(
        "bank_statement_lines",
        sa.Column(
            "matched_journal_line_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="banking",
    )
