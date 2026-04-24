"""Replace fixed-asset statuses with operational statuses.

Revision ID: 20260424_replace_fa_asset_statuses
Revises: 20260415_add_statement_line_number_uniqueness, 20260416_add_fa_asset_current_depreciation_schedule_column, f8c4a2c1e9bf
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260424_replace_fa_asset_statuses"
down_revision = (
    "20260415_add_statement_line_number_uniqueness",
    "20260416_add_fa_asset_current_depreciation_schedule_column",
    "f8c4a2c1e9bf",
)
branch_labels = None
depends_on = None

OLD_TYPE = "asset_status"
NEW_TYPE = "asset_status_new"
OLD_VALUES = (
    "DRAFT",
    "ACTIVE",
    "FULLY_DEPRECIATED",
    "DISPOSED",
    "IMPAIRED",
    "UNDER_CONSTRUCTION",
)
NEW_VALUES = (
    "NOT_IN_USE",
    "IN_USE",
    "IN_STORE",
    "FAULTY",
    "UNDER_REPAIR",
    "FULLY_DEPRECIATED",
    "RETIRED",
)


def _enum_labels(conn: sa.engine.Connection, type_name: str) -> list[str]:
    rows = conn.execute(
        sa.text(
            """
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = to_regtype(:type_name)
            ORDER BY enumsortorder
            """
        ),
        {"type_name": type_name},
    ).fetchall()
    return [row[0] for row in rows]


def _type_exists(conn: sa.engine.Connection, type_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_type
                WHERE typname = :type_name
                """
            ),
            {"type_name": type_name},
        ).first()
        is not None
    )


def _asset_table_exists(conn: sa.engine.Connection) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'fa' AND table_name = 'asset'
                """
            )
        ).first()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _asset_table_exists(conn) or not _type_exists(conn, OLD_TYPE):
        return

    if tuple(_enum_labels(conn, OLD_TYPE)) == NEW_VALUES:
        conn.execute(
            sa.text(
                """
                ALTER TABLE fa.asset
                ALTER COLUMN status SET DEFAULT 'NOT_IN_USE'::asset_status
                """
            )
        )
        return

    conn.execute(
        sa.text(
            """
            CREATE TYPE asset_status_new AS ENUM (
                'NOT_IN_USE',
                'IN_USE',
                'IN_STORE',
                'FAULTY',
                'UNDER_REPAIR',
                'FULLY_DEPRECIATED',
                'RETIRED'
            )
            """
        )
    )
    conn.execute(sa.text("ALTER TABLE fa.asset ALTER COLUMN status DROP DEFAULT"))
    conn.execute(
        sa.text(
            """
            ALTER TABLE fa.asset
            ALTER COLUMN status TYPE asset_status_new
            USING (
                CASE status::text
                    WHEN 'DRAFT' THEN 'NOT_IN_USE'
                    WHEN 'ACTIVE' THEN 'IN_USE'
                    WHEN 'FULLY_DEPRECIATED' THEN 'FULLY_DEPRECIATED'
                    WHEN 'DISPOSED' THEN 'RETIRED'
                    WHEN 'IMPAIRED' THEN 'FAULTY'
                    WHEN 'UNDER_CONSTRUCTION' THEN 'IN_STORE'
                END
            )::asset_status_new
            """
        )
    )
    conn.execute(sa.text("DROP TYPE asset_status"))
    conn.execute(sa.text("ALTER TYPE asset_status_new RENAME TO asset_status"))
    conn.execute(
        sa.text(
            """
            ALTER TABLE fa.asset
            ALTER COLUMN status SET DEFAULT 'NOT_IN_USE'::asset_status
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _asset_table_exists(conn) or not _type_exists(conn, OLD_TYPE):
        return

    if tuple(_enum_labels(conn, OLD_TYPE)) == OLD_VALUES:
        conn.execute(
            sa.text(
                """
                ALTER TABLE fa.asset
                ALTER COLUMN status SET DEFAULT 'DRAFT'::asset_status
                """
            )
        )
        return

    conn.execute(
        sa.text(
            """
            CREATE TYPE asset_status_old AS ENUM (
                'DRAFT',
                'ACTIVE',
                'FULLY_DEPRECIATED',
                'DISPOSED',
                'IMPAIRED',
                'UNDER_CONSTRUCTION'
            )
            """
        )
    )
    conn.execute(sa.text("ALTER TABLE fa.asset ALTER COLUMN status DROP DEFAULT"))
    conn.execute(
        sa.text(
            """
            ALTER TABLE fa.asset
            ALTER COLUMN status TYPE asset_status_old
            USING (
                CASE status::text
                    WHEN 'NOT_IN_USE' THEN 'DRAFT'
                    WHEN 'IN_USE' THEN 'ACTIVE'
                    WHEN 'IN_STORE' THEN 'UNDER_CONSTRUCTION'
                    WHEN 'FAULTY' THEN 'IMPAIRED'
                    WHEN 'UNDER_REPAIR' THEN 'IMPAIRED'
                    WHEN 'FULLY_DEPRECIATED' THEN 'FULLY_DEPRECIATED'
                    WHEN 'RETIRED' THEN 'DISPOSED'
                END
            )::asset_status_old
            """
        )
    )
    conn.execute(sa.text("DROP TYPE asset_status"))
    conn.execute(sa.text("ALTER TYPE asset_status_old RENAME TO asset_status"))
    conn.execute(
        sa.text(
            """
            ALTER TABLE fa.asset
            ALTER COLUMN status SET DEFAULT 'DRAFT'::asset_status
            """
        )
    )
