"""Apply fixed-asset category structure updates.

Revision ID: 20260424_apply_fa_category_structure_updates
Revises: 20260424_replace_fa_asset_statuses
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260424_apply_fa_category_structure_updates"
down_revision = "20260424_replace_fa_asset_statuses"
branch_labels = None
depends_on = None


def _category_rows(conn: sa.engine.Connection, code: str) -> list[sa.Row]:
    return list(
        conn.execute(
            sa.text(
                """
                SELECT
                    category_id,
                    organization_id,
                    category_code,
                    category_name,
                    description,
                    parent_category_id,
                    depreciation_method,
                    useful_life_months,
                    residual_value_percent,
                    asset_account_id,
                    accumulated_depreciation_account_id,
                    depreciation_expense_account_id,
                    gain_loss_disposal_account_id,
                    revaluation_surplus_account_id,
                    impairment_loss_account_id,
                    capitalization_threshold,
                    revaluation_model_allowed,
                    is_active
                FROM fa.asset_category
                WHERE category_code = :code
                """
            ),
            {"code": code},
        )
    )


def _category_id(
    conn: sa.engine.Connection, organization_id: str, code: str
) -> str | None:
    row = conn.execute(
        sa.text(
            """
            SELECT category_id
            FROM fa.asset_category
            WHERE organization_id = :organization_id
              AND category_code = :code
            """
        ),
        {"organization_id": organization_id, "code": code},
    ).first()
    return str(row.category_id) if row else None


def _insert_clone(
    conn: sa.engine.Connection,
    template: sa.Row,
    new_code: str,
    new_name: str,
) -> None:
    if _category_id(conn, str(template.organization_id), new_code):
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO fa.asset_category (
                category_id,
                organization_id,
                category_code,
                category_name,
                description,
                parent_category_id,
                depreciation_method,
                useful_life_months,
                residual_value_percent,
                asset_account_id,
                accumulated_depreciation_account_id,
                depreciation_expense_account_id,
                gain_loss_disposal_account_id,
                revaluation_surplus_account_id,
                impairment_loss_account_id,
                capitalization_threshold,
                revaluation_model_allowed,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                :organization_id,
                :category_code,
                :category_name,
                :description,
                :parent_category_id,
                :depreciation_method,
                :useful_life_months,
                :residual_value_percent,
                :asset_account_id,
                :accumulated_depreciation_account_id,
                :depreciation_expense_account_id,
                :gain_loss_disposal_account_id,
                :revaluation_surplus_account_id,
                :impairment_loss_account_id,
                :capitalization_threshold,
                :revaluation_model_allowed,
                true,
                now(),
                now()
            )
            """
        ),
        {
            "organization_id": str(template.organization_id),
            "category_code": new_code,
            "category_name": new_name,
            "description": template.description,
            "parent_category_id": (
                str(template.parent_category_id) if template.parent_category_id else None
            ),
            "depreciation_method": template.depreciation_method,
            "useful_life_months": template.useful_life_months,
            "residual_value_percent": template.residual_value_percent,
            "asset_account_id": str(template.asset_account_id),
            "accumulated_depreciation_account_id": str(
                template.accumulated_depreciation_account_id
            ),
            "depreciation_expense_account_id": str(
                template.depreciation_expense_account_id
            ),
            "gain_loss_disposal_account_id": str(
                template.gain_loss_disposal_account_id
            ),
            "revaluation_surplus_account_id": (
                str(template.revaluation_surplus_account_id)
                if template.revaluation_surplus_account_id
                else None
            ),
            "impairment_loss_account_id": (
                str(template.impairment_loss_account_id)
                if template.impairment_loss_account_id
                else None
            ),
            "capitalization_threshold": template.capitalization_threshold,
            "revaluation_model_allowed": template.revaluation_model_allowed,
        },
    )


def _set_active(
    conn: sa.engine.Connection, organization_id: str, code: str, is_active: bool
) -> None:
    conn.execute(
        sa.text(
            """
            UPDATE fa.asset_category
            SET is_active = :is_active,
                updated_at = now()
            WHERE organization_id = :organization_id
              AND category_code = :code
            """
        ),
        {
            "organization_id": organization_id,
            "code": code,
            "is_active": is_active,
        },
    )


def _set_parent(
    conn: sa.engine.Connection,
    organization_id: str,
    code: str,
    parent_code: str | None,
) -> None:
    parent_id = _category_id(conn, organization_id, parent_code) if parent_code else None
    conn.execute(
        sa.text(
            """
            UPDATE fa.asset_category
            SET parent_category_id = :parent_category_id,
                updated_at = now()
            WHERE organization_id = :organization_id
              AND category_code = :code
            """
        ),
        {
            "organization_id": organization_id,
            "code": code,
            "parent_category_id": parent_id,
        },
    )


def upgrade() -> None:
    conn = op.get_bind()

    office_equipment_rows = _category_rows(conn, "OFFICE_EQUIPMENT")
    for row in office_equipment_rows:
        _set_parent(conn, str(row.organization_id), "OFFICE_EQUIPMENT", "OFFADMIN")

    pantry_rows = _category_rows(conn, "PANTRY-APPL")
    for row in pantry_rows:
        _insert_clone(conn, row, "PANTRY-DISP", "Water Dispensers")
        _insert_clone(conn, row, "PANTRY-MICRO", "Microwaves")
        _insert_clone(conn, row, "PANTRY-REFR", "Refrigerators")
        _set_active(conn, str(row.organization_id), "PANTRY-APPL", False)

    print_rows = _category_rows(conn, "OFF-PRINT")
    for row in print_rows:
        _insert_clone(conn, row, "OFF-PRINTER", "Printers")
        _insert_clone(conn, row, "OFF-SCANNER", "Scanners")
        _insert_clone(conn, row, "OFF-PHOTOCOPY", "Photocopiers")
        _set_active(conn, str(row.organization_id), "OFF-PRINT", False)

    office_rows = _category_rows(conn, "OFFICE_EQUIPMENT")
    for row in office_rows:
        _insert_clone(conn, row, "OFF-BIND", "Binding Machines")
        _insert_clone(conn, row, "OFF-BCOUNT", "Bill Counters")
        _insert_clone(conn, row, "OFF-SHRED", "Paper Shredders")
        _insert_clone(conn, row, "OFF-SAFE", "Iron Safes")

    power_rows = _category_rows(conn, "PWR-SOLAR")
    for row in power_rows:
        _insert_clone(conn, row, "PWR-GEN", "Generators")


def downgrade() -> None:
    conn = op.get_bind()

    office_equipment_rows = _category_rows(conn, "OFFICE_EQUIPMENT")
    for row in office_equipment_rows:
        _set_parent(conn, str(row.organization_id), "OFFICE_EQUIPMENT", None)

    pantry_rows = _category_rows(conn, "PANTRY-APPL")
    for row in pantry_rows:
        _set_active(conn, str(row.organization_id), "PANTRY-APPL", True)
        _set_active(conn, str(row.organization_id), "PANTRY-DISP", False)
        _set_active(conn, str(row.organization_id), "PANTRY-MICRO", False)
        _set_active(conn, str(row.organization_id), "PANTRY-REFR", False)

    print_rows = _category_rows(conn, "OFF-PRINT")
    for row in print_rows:
        _set_active(conn, str(row.organization_id), "OFF-PRINT", True)
        _set_active(conn, str(row.organization_id), "OFF-PRINTER", False)
        _set_active(conn, str(row.organization_id), "OFF-SCANNER", False)
        _set_active(conn, str(row.organization_id), "OFF-PHOTOCOPY", False)

    for row in office_equipment_rows:
        _set_active(conn, str(row.organization_id), "OFF-BIND", False)
        _set_active(conn, str(row.organization_id), "OFF-BCOUNT", False)
        _set_active(conn, str(row.organization_id), "OFF-SHRED", False)
        _set_active(conn, str(row.organization_id), "OFF-SAFE", False)

    power_rows = _category_rows(conn, "PWR-SOLAR")
    for row in power_rows:
        _set_active(conn, str(row.organization_id), "PWR-GEN", False)
