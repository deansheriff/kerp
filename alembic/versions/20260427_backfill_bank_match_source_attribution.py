"""Backfill source_type/source_id on bank_statement_line_matches.

FY2025 audit (2026-04-27) finding P1-2: 39,485 of 39,517 FY2025 bank-line
match rows had NULL ``source_type``/``source_id`` because
``multi_match_statement_line()`` was creating ``BankStatementLineMatch`` rows
without these audit-trail columns. The companion code fix in
``app/services/finance/banking/reconciliation_parts/matching.py`` now derives
both columns from the linked journal entry on insert.

This one-shot backfill repairs the historical rows by:
  1. Setting ``source_type`` from the linked ``journal_entry.source_document_type``.
  2. Setting ``source_id`` from ``journal_entry.source_document_id`` where the
     journal entry has it.
  3. For ``CUSTOMER_PAYMENT`` rows still missing ``source_id``, reverse-look up
     ``ar.customer_payment.payment_id`` via ``customer_payment.journal_entry_id``.
  4. Same reverse lookup for ``SUPPLIER_PAYMENT`` rows via ``ap.supplier_payment``.

Idempotent: each statement only updates rows that still have NULL columns.
Reverse-lookup coverage on the FY2025 dev data: 97% of CUSTOMER_PAYMENT rows
and 98% of SUPPLIER_PAYMENT rows recover a ``source_id``. Manual journals
(JOURNAL, BANK_FEE, INTERBANK_TRANSFER, etc.) never had a source document,
so their ``source_id`` correctly stays NULL.

Revision ID: 20260427_backfill_match_source
Revises: 20260427_audit_cleanup
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op


revision = "20260427_backfill_match_source"
down_revision = "20260427_audit_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Source type from journal_entry.source_document_type.
    op.execute(
        """
        UPDATE banking.bank_statement_line_matches m
        SET source_type = je.source_document_type
        FROM gl.journal_entry_line jel
        JOIN gl.journal_entry je ON je.journal_entry_id = jel.journal_entry_id
        WHERE jel.line_id = m.journal_line_id
          AND (m.source_type IS NULL OR m.source_type = '')
          AND je.source_document_type IS NOT NULL
        """
    )

    # 2. Source id from journal_entry.source_document_id (when populated there).
    op.execute(
        """
        UPDATE banking.bank_statement_line_matches m
        SET source_id = je.source_document_id
        FROM gl.journal_entry_line jel
        JOIN gl.journal_entry je ON je.journal_entry_id = jel.journal_entry_id
        WHERE jel.line_id = m.journal_line_id
          AND m.source_id IS NULL
          AND je.source_document_id IS NOT NULL
        """
    )

    # 3. Reverse lookup for CUSTOMER_PAYMENT rows where journal_entry didn't
    #    carry source_document_id but customer_payment has journal_entry_id.
    op.execute(
        """
        UPDATE banking.bank_statement_line_matches m
        SET source_id = cp.payment_id
        FROM gl.journal_entry_line jel
        JOIN gl.journal_entry je ON je.journal_entry_id = jel.journal_entry_id
        JOIN ar.customer_payment cp ON cp.journal_entry_id = je.journal_entry_id
        WHERE jel.line_id = m.journal_line_id
          AND m.source_id IS NULL
          AND m.source_type = 'CUSTOMER_PAYMENT'
        """
    )

    # 4. Reverse lookup for SUPPLIER_PAYMENT rows.
    op.execute(
        """
        UPDATE banking.bank_statement_line_matches m
        SET source_id = sp.payment_id
        FROM gl.journal_entry_line jel
        JOIN gl.journal_entry je ON je.journal_entry_id = jel.journal_entry_id
        JOIN ap.supplier_payment sp ON sp.journal_entry_id = je.journal_entry_id
        WHERE jel.line_id = m.journal_line_id
          AND m.source_id IS NULL
          AND m.source_type = 'SUPPLIER_PAYMENT'
        """
    )


def downgrade() -> None:
    # No-op: a backfill cannot be cleanly reversed without losing audit
    # information that legitimately accumulated after the upgrade. If the
    # caller really needs to clear the columns, do it manually.
    pass
