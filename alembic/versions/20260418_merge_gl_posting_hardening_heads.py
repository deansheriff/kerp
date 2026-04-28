"""Merge GL posting hardening migration heads.

Revision ID: 20260418_merge_gl_posting_heads
Revises: 20260418_add_posting_batch_journal_entry_id, 20260418_harden_gl_posting
Create Date: 2026-04-18
"""

from __future__ import annotations


revision = "20260418_merge_gl_posting_heads"
down_revision = (
    "20260418_add_posting_batch_journal_entry_id",
    "20260418_harden_gl_posting",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
