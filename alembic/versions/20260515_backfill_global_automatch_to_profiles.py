"""Backfill GLOBAL banking.automatch_* settings into every org's profile.

The earlier ``20260515_backfill_automatch_profile`` migration only copied
ORG-SPECIFIC ``banking.automatch_*`` DomainSettings into each org's profile.
Global rows (``organization_id IS NULL``) were intentionally deferred —
they implicitly apply to every org via the legacy
``AutoReconciliationCoreService._load_config`` reader.

This migration finishes the job: for every active profile, apply any
non-NULL global setting to a corresponding NULL profile column.  Operator
values on the profile are never overwritten (COALESCE).

After this migration, every org's profile holds the explicit values that
will be used at runtime — the legacy ``_load_config`` reader becomes safe
to remove in a follow-up code change.

Edge case: orgs with NO active profile.  This migration does NOT create
profile rows for them; the policy service's fallback (resolve → returns
defaults when no profile exists) continues to handle that case.

Revision ID: 20260515_backfill_global_automatch
Revises: 20260515_drop_legacy_matched_jl_id
Create Date: 2026-05-15
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_backfill_global_automatch"
down_revision: str | None = "20260515_drop_legacy_matched_jl_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)


_KEY_TO_COLUMN: dict[str, str] = {
    "automatch_pass_payment_intents_enabled": "pass_payment_intents_enabled",
    "automatch_pass_splynx_by_ref_enabled": "pass_splynx_by_ref_enabled",
    "automatch_pass_splynx_date_amount_enabled": "pass_splynx_date_amount_enabled",
    "automatch_pass_ap_payments_enabled": "pass_ap_payments_enabled",
    "automatch_pass_ar_payments_enabled": "pass_ar_payments_enabled",
    "automatch_pass_bank_fees_enabled": "pass_bank_fees_enabled",
    "automatch_pass_settlements_enabled": "pass_settlements_enabled",
    "automatch_amount_tolerance_cents": "amount_tolerance_cents",
    "automatch_date_buffer_days": "date_buffer_days",
    "automatch_settlement_date_window_days": "settlement_window_days",
    "automatch_finance_cost_account_code": "finance_cost_account_code",
}

_BOOLEAN_KEYS: frozenset[str] = frozenset(
    {
        "automatch_pass_payment_intents_enabled",
        "automatch_pass_splynx_by_ref_enabled",
        "automatch_pass_splynx_date_amount_enabled",
        "automatch_pass_ap_payments_enabled",
        "automatch_pass_ar_payments_enabled",
        "automatch_pass_bank_fees_enabled",
        "automatch_pass_settlements_enabled",
    }
)

_INTEGER_KEYS: frozenset[str] = frozenset(
    {
        "automatch_amount_tolerance_cents",
        "automatch_date_buffer_days",
        "automatch_settlement_date_window_days",
    }
)


def _parse_setting_value(key: str, value_text: str | None, value_json: Any) -> Any:
    """Mirror the parser in ``20260515_backfill_automatch_to_profile``.

    Returns the coerced value or ``None`` when the setting has no value or
    fails to parse cleanly.
    """
    raw: Any
    if value_text is not None:
        raw = value_text
    elif value_json is not None:
        raw = value_json
    else:
        return None

    if key in _BOOLEAN_KEYS:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return None

    if key in _INTEGER_KEYS:
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            try:
                return int(raw.strip())
            except (ValueError, AttributeError):
                return None
        return None

    if raw is None:
        return None
    return str(raw).strip() or None


def upgrade() -> None:
    bind = op.get_bind()

    # Collect every active global banking.automatch_* setting.
    global_rows = bind.execute(
        sa.text(
            """
            SELECT key, value_text, value_json
            FROM domain_settings
            WHERE domain = 'banking'
              AND key LIKE 'automatch\\_%' ESCAPE '\\'
              AND organization_id IS NULL
              AND is_active = TRUE
            """
        )
    ).fetchall()

    global_values: dict[str, Any] = {}
    for key, value_text, value_json in global_rows:
        column = _KEY_TO_COLUMN.get(key)
        if not column:
            continue
        parsed = _parse_setting_value(key, value_text, value_json)
        if parsed is None:
            continue
        global_values[column] = parsed

    if not global_values:
        logger.info(
            "No global banking.automatch_* settings to materialise into profiles."
        )
        return

    # Apply each global value to every active profile, only filling NULLs
    # (operator-set values + values backfilled by the prior org-specific
    # migration are both preserved by COALESCE).
    profile_ids = (
        bind.execute(
            sa.text(
                """
            SELECT policy_id
            FROM banking.reconciliation_policy_profile
            WHERE is_active = TRUE
            """
            )
        )
        .scalars()
        .all()
    )

    if not profile_ids:
        logger.info("No active reconciliation_policy_profile rows to update.")
        return

    logger.info(
        "Backfilling %d global automatch_* setting(s) into %d active profile(s)",
        len(global_values),
        len(profile_ids),
    )

    set_clauses: list[str] = []
    params: dict[str, Any] = {}
    for column, value in global_values.items():
        placeholder = f"{column}_v"
        # Column names sourced from a fixed dict literal — safe to interpolate.
        set_clauses.append(f"{column} = COALESCE({column}, :{placeholder})")
        params[placeholder] = value

    bind.execute(
        sa.text(
            f"""
            UPDATE banking.reconciliation_policy_profile
            SET {", ".join(set_clauses)}
            WHERE is_active = TRUE
            """
        ),
        params,
    )


def downgrade() -> None:
    """No-op.

    Reversing requires distinguishing values we wrote from values an
    operator (or the prior org-specific backfill) wrote.  We can't tell
    them apart, so the safe choice is to leave the profile rows alone.
    Anyone needing a true revert should downgrade past
    ``20260515_extend_recon_profile``.
    """
    return
