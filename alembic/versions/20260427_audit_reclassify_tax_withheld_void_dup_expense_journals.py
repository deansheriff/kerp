"""Reclassify tax-withheld accounts to ASSETS and VOID duplicate expense journals.

FY2025 audit (2026-04-27) findings P2-4 and P2-1.

P2-4: Accounts 4030 ``Stampduty Deducted At Source`` and 4031 ``Value Added Tax
Withheld`` are misclassified under the REVENUE ``ifrs_category``. Economically
they are receivables from the tax authority (debit balances representing tax
already withheld at source by the customer on the entity's behalf). Move them
to the org's top-level ASSETS category. This is a presentation-only change
(IAS 8.42 — correction of prior-period classification error); GL debit/credit
balances are untouched.

P2-1: 45 duplicate ``APPROVED`` expense-reimbursement journals exist where a
``POSTED`` twin (same ``source_document_id``) already reached the ledger.
Set their status to ``VOID`` so they cannot be re-posted.

This revision is a 2-way merge: it joins the upstream chain head
(``20260427_add_contract_sequence_type``) with the local-only GL-posting
hardening branch (``20260424_merge_gl_and_fa_status_heads``) which has been
applied to dev databases but not yet committed to upstream.

Revision ID: 20260427_audit_cleanup
Revises: 20260427_add_contract_sequence_type, 20260424_merge_gl_and_fa_status_heads
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op


revision = "20260427_audit_cleanup"
down_revision = (
    "20260427_add_contract_sequence_type",
    "20260424_merge_gl_and_fa_status_heads",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Reclassify tax-withheld accounts from REVENUE to ASSETS.
    #    Idempotent: only matches accounts still in a REVENUE-categorised slot.
    op.execute(
        """
        UPDATE gl.account a
        SET category_id = ac_assets.category_id,
            updated_at = now()
        FROM gl.account_category ac_current,
             gl.account_category ac_assets
        WHERE a.category_id = ac_current.category_id
          AND ac_current.ifrs_category = 'REVENUE'
          AND ac_assets.organization_id = a.organization_id
          AND ac_assets.category_code = 'ASSETS'
          AND a.account_code IN ('4030', '4031')
          AND a.account_name IN (
              'Value Added Tax Withheld',
              'Stampduty Deducted At Source'
          )
        """
    )

    # 2. VOID duplicate APPROVED expense journals where a POSTED twin exists.
    #    Idempotent: VOIDed rows no longer match the APPROVED filter.
    #    ``source_module`` casing is mixed across the dataset (legacy import
    #    drift — both 'expense' and 'EXPENSE' exist), hence LOWER().
    op.execute(
        """
        UPDATE gl.journal_entry je
        SET status = 'VOID'
        WHERE je.status = 'APPROVED'
          AND LOWER(je.source_module) = 'expense'
          AND je.source_document_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM gl.journal_entry je2
              WHERE je2.source_document_id = je.source_document_id
                AND LOWER(je2.source_module) = 'expense'
                AND je2.status = 'POSTED'
                AND je2.journal_entry_id != je.journal_entry_id
          )
        """
    )


def downgrade() -> None:
    # Reverse the VOID first (the category move depends on accounts existing,
    # so order is independent — but doing data-state changes before classification
    # changes keeps the audit trail clean if downgrade fails midway).
    op.execute(
        """
        UPDATE gl.journal_entry je
        SET status = 'APPROVED'
        WHERE je.status = 'VOID'
          AND LOWER(je.source_module) = 'expense'
          AND je.source_document_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM gl.journal_entry je2
              WHERE je2.source_document_id = je.source_document_id
                AND LOWER(je2.source_module) = 'expense'
                AND je2.status = 'POSTED'
                AND je2.journal_entry_id != je.journal_entry_id
          )
        """
    )

    # Move tax-withheld accounts back to the REVENUE (REV) category.
    op.execute(
        """
        UPDATE gl.account a
        SET category_id = ac_rev.category_id,
            updated_at = now()
        FROM gl.account_category ac_current,
             gl.account_category ac_rev
        WHERE a.category_id = ac_current.category_id
          AND ac_current.ifrs_category = 'ASSETS'
          AND ac_rev.organization_id = a.organization_id
          AND ac_rev.category_code = 'REV'
          AND a.account_code IN ('4030', '4031')
          AND a.account_name IN (
              'Value Added Tax Withheld',
              'Stampduty Deducted At Source'
          )
        """
    )
