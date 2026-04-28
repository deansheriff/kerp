"""Flatten fixed-asset category assignments to top-level categories.

Revision ID: 20260427_flatten_fixed_asset_categories
Revises: 20260427_reconcile_vat_taxpro
Create Date: 2026-04-27 14:55:00
"""

from alembic import op


revision = "20260427_flatten_fixed_asset_categories"
down_revision = "20260427_reconcile_vat_taxpro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Walk parent_category_id all the way to the root using a recursive CTE.
    # The single-level UPDATE this replaces would leave assets pointing at a
    # mid-level child if the original tree was deeper than two levels.
    # ``cycle`` detection terminates if the data accidentally forms a loop.
    op.execute(
        """
        WITH RECURSIVE category_root AS (
            SELECT
                category_id,
                parent_category_id,
                category_id AS root_id,
                1 AS depth
            FROM fa.asset_category

            UNION ALL

            SELECT
                cr.category_id,
                parent.parent_category_id,
                parent.category_id AS root_id,
                cr.depth + 1 AS depth
            FROM category_root cr
            JOIN fa.asset_category parent
              ON parent.category_id = cr.parent_category_id
            WHERE cr.depth < 16
        ),
        roots AS (
            SELECT DISTINCT ON (category_id)
                category_id,
                root_id
            FROM category_root
            WHERE parent_category_id IS NULL
            ORDER BY category_id, depth DESC
        )
        UPDATE fa.asset AS asset
        SET category_id = roots.root_id
        FROM roots
        WHERE asset.category_id = roots.category_id
          AND asset.category_id <> roots.root_id
        """
    )


def downgrade() -> None:
    # Irreversible data migration: previous child category assignments are not restored.
    pass
