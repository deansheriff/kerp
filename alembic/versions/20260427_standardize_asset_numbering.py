"""Standardize fixed-asset numbering to DT-AST-0001.

Revision ID: 20260427_standardize_asset_numbering
Revises: 20260424_apply_fa_category_structure_updates
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op

revision = "20260427_standardize_asset_numbering"
down_revision = "20260424_apply_fa_category_structure_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH org_asset_counts AS (
            SELECT organization_id, COUNT(*)::bigint AS asset_count
            FROM fa.asset
            GROUP BY organization_id
        )
        INSERT INTO core_config.numbering_sequence (
            sequence_id,
            organization_id,
            sequence_type,
            prefix,
            suffix,
            separator,
            min_digits,
            include_year,
            include_month,
            year_format,
            current_number,
            current_year,
            current_month,
            reset_frequency,
            fiscal_year_reset,
            fiscal_year_id,
            last_used_at,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            org_asset_counts.organization_id,
            'ASSET',
            'DT-AST',
            '',
            '-',
            4,
            FALSE,
            FALSE,
            4,
            org_asset_counts.asset_count,
            NULL,
            NULL,
            'NEVER',
            FALSE,
            NULL,
            NULL,
            now(),
            now()
        FROM org_asset_counts
        WHERE NOT EXISTS (
            SELECT 1
            FROM core_config.numbering_sequence existing
            WHERE existing.organization_id = org_asset_counts.organization_id
              AND existing.sequence_type = 'ASSET'
        )
        """
    )

    op.execute(
        """
        UPDATE core_config.numbering_sequence sequence
        SET
            prefix = 'DT-AST',
            suffix = '',
            separator = '-',
            min_digits = 4,
            include_year = FALSE,
            include_month = FALSE,
            year_format = 4,
            current_year = NULL,
            current_month = NULL,
            reset_frequency = 'NEVER',
            updated_at = now()
        WHERE sequence.sequence_type = 'ASSET'
        """
    )

    op.execute(
        """
        WITH ranked_assets AS (
            SELECT
                asset_id,
                'TMP-AST-' || substr(replace(asset_id::text, '-', ''), 1, 20) AS temp_number
            FROM fa.asset
        )
        UPDATE fa.asset asset
        SET asset_number = ranked_assets.temp_number
        FROM ranked_assets
        WHERE asset.asset_id = ranked_assets.asset_id
        """
    )

    op.execute(
        """
        WITH ranked_assets AS (
            SELECT
                asset_id,
                CASE
                    WHEN length(row_number() OVER (
                        PARTITION BY organization_id
                        ORDER BY created_at, asset_id
                    )::text) >= 4
                        THEN row_number() OVER (
                            PARTITION BY organization_id
                            ORDER BY created_at, asset_id
                        )::text
                    ELSE lpad(
                        row_number() OVER (
                            PARTITION BY organization_id
                            ORDER BY created_at, asset_id
                        )::text,
                        4,
                        '0'
                    )
                END AS seq_text
            FROM fa.asset
        )
        UPDATE fa.asset asset
        SET asset_number = 'DT-AST-' || ranked_assets.seq_text
        FROM ranked_assets
        WHERE asset.asset_id = ranked_assets.asset_id
        """
    )

    op.execute(
        """
        WITH org_asset_counts AS (
            SELECT organization_id, COUNT(*)::bigint AS asset_count
            FROM fa.asset
            GROUP BY organization_id
        )
        UPDATE core_config.numbering_sequence sequence
        SET
            current_number = COALESCE(org_asset_counts.asset_count, 0),
            updated_at = now()
        FROM org_asset_counts
        WHERE sequence.sequence_type = 'ASSET'
          AND sequence.organization_id = org_asset_counts.organization_id
        """
    )

    op.execute(
        """
        UPDATE core_config.numbering_sequence sequence
        SET
            current_number = 0,
            updated_at = now()
        WHERE sequence.sequence_type = 'ASSET'
          AND NOT EXISTS (
              SELECT 1
              FROM fa.asset asset
              WHERE asset.organization_id = sequence.organization_id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE core_config.numbering_sequence sequence
        SET
            prefix = 'FA',
            suffix = '',
            separator = '-',
            min_digits = 4,
            include_year = TRUE,
            include_month = TRUE,
            year_format = 4,
            reset_frequency = 'MONTHLY',
            updated_at = now()
        WHERE sequence.sequence_type = 'ASSET'
        """
    )
