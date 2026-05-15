"""Backfill BankStatementLineMatch junction for existing Splynx-matched lines.

Before this migration, the Splynx sync's ``_mark_line_matched`` set
``is_matched=true`` and appended a free-text note like
``"[Matched to Splynx payment <UUID> by date+amount]"`` but never wrote
to the legacy ``matched_journal_line_id`` column nor to the
``bank_statement_line_matches`` junction.

Those bank lines therefore look matched to the UI but have no structured
link to the underlying ``ar.customer_payment`` row or the GL journal —
dashboards and detail views drop them.

This migration:
1. Scans bank_statement_lines where ``is_matched=true`` AND notes
   contains ``"Matched to Splynx payment <UUID>"`` AND there's no
   existing junction row.
2. Parses the payment UUID from the note.
3. Looks up the payment's POSTED journal entry (via correlation_id) and
   the bank-side GL line on that journal.
4. Inserts a ``BankStatementLineMatch`` row with
   source_type='CUSTOMER_PAYMENT' so downstream readers treat it
   identically to a fresh auto-recon match.
5. Sets the legacy ``matched_journal_line_id`` for forward compat
   (dual-write is still active in active matchers).

Idempotent: skips any line that already has a junction row.

Revision ID: 20260515_backfill_splynx_match_junction
Revises: 20260515_backfill_automatch_profile
Create Date: 2026-05-15
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_backfill_splynx_match_junction"
down_revision: str | None = "20260515_backfill_automatch_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)

# Matches the Splynx note format: "Matched to Splynx payment <UUID> by ..."
# UUIDs are case-insensitive, hyphens at canonical positions.
_NOTE_PAYMENT_RE = re.compile(
    r"Matched to Splynx payment\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def _extract_payment_id(notes: str | None) -> uuid.UUID | None:
    if not notes:
        return None
    m = _NOTE_PAYMENT_RE.search(notes)
    if not m:
        return None
    try:
        return uuid.UUID(m.group(1))
    except (ValueError, AttributeError):
        return None


def upgrade() -> None:
    bind = op.get_bind()

    # Candidates: matched lines whose notes mention a Splynx payment AND
    # which have NO junction row yet.  The LEFT JOIN + IS NULL pattern is
    # the canonical way to find "absences".
    rows = bind.execute(
        sa.text(
            """
            SELECT bsl.line_id, bsl.notes
            FROM banking.bank_statement_lines bsl
            LEFT JOIN banking.bank_statement_line_matches m
              ON m.statement_line_id = bsl.line_id
            WHERE bsl.is_matched = TRUE
              AND m.match_id IS NULL
              AND bsl.notes IS NOT NULL
              AND bsl.notes LIKE '%Matched to Splynx payment %'
            """
        )
    ).fetchall()

    if not rows:
        logger.info("No detached Splynx-matched lines to backfill.")
        return

    logger.info(
        "Found %d Splynx-matched bank lines without junction rows — backfilling",
        len(rows),
    )

    inserted = 0
    skipped_no_uuid = 0
    skipped_no_journal = 0

    for row in rows:
        line_id, notes = row.line_id, row.notes
        payment_id = _extract_payment_id(notes)
        if payment_id is None:
            skipped_no_uuid += 1
            continue

        # Resolve the bank-side journal line for this payment.  The Splynx
        # CustomerPayment is created with correlation_id='splynx-pmt-<id>'
        # and a posted journal entry by the sync.  Matching against the
        # bank account's gl_account_id ensures we pick the bank-side line.
        journal_line_id = bind.execute(
            sa.text(
                """
                SELECT jel.line_id
                FROM ar.customer_payment cp
                JOIN gl.journal_entry je
                  ON je.correlation_id = cp.correlation_id
                 AND je.organization_id = cp.organization_id
                 AND je.status = 'POSTED'
                JOIN gl.journal_entry_line jel
                  ON jel.journal_entry_id = je.journal_entry_id
                JOIN banking.bank_accounts ba
                  ON ba.bank_account_id = cp.bank_account_id
                WHERE cp.payment_id = :payment_id
                  AND jel.account_id = ba.gl_account_id
                LIMIT 1
                """
            ),
            {"payment_id": payment_id},
        ).scalar()

        if journal_line_id is None:
            skipped_no_journal += 1
            continue

        # Insert the junction row. ON CONFLICT DO NOTHING covers the
        # extremely-unlikely race where another process beat us to it.
        bind.execute(
            sa.text(
                """
                INSERT INTO banking.bank_statement_line_matches
                    (match_id, statement_line_id, journal_line_id,
                     match_type, source_type, source_id, is_primary)
                VALUES
                    (gen_random_uuid(), :line_id, :journal_line_id,
                     'AUTO', 'CUSTOMER_PAYMENT', :payment_id, TRUE)
                ON CONFLICT (statement_line_id, journal_line_id) DO NOTHING
                """
            ),
            {
                "line_id": line_id,
                "journal_line_id": journal_line_id,
                "payment_id": payment_id,
            },
        )

        # Dual-write to the legacy column (still consumed by some readers
        # until #12 stage 2 ships).  COALESCE preserves any pre-existing
        # value rather than clobbering it.
        bind.execute(
            sa.text(
                """
                UPDATE banking.bank_statement_lines
                SET matched_journal_line_id =
                        COALESCE(matched_journal_line_id, :journal_line_id)
                WHERE line_id = :line_id
                """
            ),
            {"line_id": line_id, "journal_line_id": journal_line_id},
        )
        inserted += 1

    logger.info(
        "Splynx match backfill complete: %d inserted, %d skipped (no UUID), "
        "%d skipped (no matching journal)",
        inserted,
        skipped_no_uuid,
        skipped_no_journal,
    )


def downgrade() -> None:
    """Remove backfill rows.

    Best-effort: deletes junction rows with source_type='CUSTOMER_PAYMENT'
    AND is_primary=TRUE AND match_type='AUTO' whose corresponding bank
    line still has the Splynx note pattern.  Doesn't touch the legacy
    matched_journal_line_id (its previous state was NULL — preserving
    the dual-write is conservative).
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM banking.bank_statement_line_matches m
            USING banking.bank_statement_lines bsl
            WHERE m.statement_line_id = bsl.line_id
              AND m.source_type = 'CUSTOMER_PAYMENT'
              AND m.match_type = 'AUTO'
              AND m.is_primary = TRUE
              AND bsl.notes LIKE '%Matched to Splynx payment %'
            """
        )
    )
