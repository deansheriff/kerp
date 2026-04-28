"""Merge GL posting and fixed-asset status heads.

Revision ID: 20260424_merge_gl_and_fa_status_heads
Revises: 20260418_merge_gl_posting_heads, 20260424_apply_fa_category_structure_updates
Create Date: 2026-04-24
"""

from __future__ import annotations


revision = "20260424_merge_gl_and_fa_status_heads"
down_revision = (
    "20260418_merge_gl_posting_heads",
    "20260424_apply_fa_category_structure_updates",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
