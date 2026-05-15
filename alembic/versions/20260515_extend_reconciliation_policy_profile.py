"""Extend reconciliation_policy_profile with AutoMatchConfig fields.

Adds the AutoMatchConfig settings (finance_cost_account_code + per-pass
enabled flags) to the profile schema so operators have a single source of
truth instead of editing DomainSettings.  All columns are nullable so an
existing profile keeps working — the policy service falls back to the
DomainSettings-backed legacy config when these fields are NULL.

Backfill (copying live DomainSettings values into profile rows) is
intentionally deferred to a follow-up.  Operators see runtime WARNINGs
(``_warn_on_divergence``) the first time the two configs diverge, which
gives a natural prompt to populate the profile.

Revision ID: 20260515_extend_recon_profile
Revises: 20260513_position_vacancy_policy
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_extend_recon_profile"
down_revision: str | None = "20260513_position_vacancy_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("finance_cost_account_code", sa.String(length=40)),
    ("pass_payment_intents_enabled", sa.Boolean()),
    ("pass_splynx_by_ref_enabled", sa.Boolean()),
    ("pass_splynx_date_amount_enabled", sa.Boolean()),
    ("pass_ap_payments_enabled", sa.Boolean()),
    ("pass_ar_payments_enabled", sa.Boolean()),
    ("pass_bank_fees_enabled", sa.Boolean()),
    ("pass_settlements_enabled", sa.Boolean()),
)


def _column_exists(table: str, column: str, schema: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    for name, column_type in _NEW_COLUMNS:
        if _column_exists("reconciliation_policy_profile", name, "banking"):
            continue
        op.add_column(
            "reconciliation_policy_profile",
            sa.Column(name, column_type, nullable=True),
            schema="banking",
        )


def downgrade() -> None:
    for name, _column_type in reversed(_NEW_COLUMNS):
        if not _column_exists("reconciliation_policy_profile", name, "banking"):
            continue
        op.drop_column(
            "reconciliation_policy_profile",
            name,
            schema="banking",
        )
