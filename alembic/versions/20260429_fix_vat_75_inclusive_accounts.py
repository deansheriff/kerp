"""Repair VAT-7.5 (inclusive) tax code GL account mappings.

Revision ID: 20260429_fix_vat_75_inclusive_accounts
Revises: 20260429_fix_deferred_input_vat
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260429_fix_vat_75_inclusive_accounts"
down_revision = "20260429_fix_deferred_input_vat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE tax.tax_code AS inclusive
            SET tax_paid_account_id = base.tax_paid_account_id,
                tax_collected_account_id = base.tax_collected_account_id
            FROM tax.tax_code AS base
            WHERE inclusive.organization_id = base.organization_id
              AND inclusive.tax_code = 'VAT-7.5 (inclusive)'
              AND base.tax_code = 'VAT-7.5'
              AND inclusive.tax_type = 'VAT'
              AND base.tax_type = 'VAT'
              AND inclusive.is_recoverable IS TRUE
              AND (
                    inclusive.tax_paid_account_id IS NULL
                 OR inclusive.tax_collected_account_id IS NULL
              )
              AND base.tax_paid_account_id IS NOT NULL
              AND base.tax_collected_account_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE tax.tax_code AS inclusive
            SET tax_paid_account_id = NULL,
                tax_collected_account_id = NULL
            FROM tax.tax_code AS base
            WHERE inclusive.organization_id = base.organization_id
              AND inclusive.tax_code = 'VAT-7.5 (inclusive)'
              AND base.tax_code = 'VAT-7.5'
              AND inclusive.tax_type = 'VAT'
              AND base.tax_type = 'VAT'
              AND inclusive.tax_paid_account_id = base.tax_paid_account_id
              AND inclusive.tax_collected_account_id = base.tax_collected_account_id
            """
        )
    )
