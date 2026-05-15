"""Backfill banking.automatch_* DomainSettings into ReconciliationPolicyProfile.

For every org that has at least one org-specific ``banking.automatch_*``
``DomainSetting``, copy the effective value into the matching column on
``banking.reconciliation_policy_profile``.  If the org has no profile row,
create one with ``name='default'``, ``is_active=true``.  Existing profile
columns are NEVER overwritten — only NULLs are filled (idempotent re-run is
safe, and operator-set values are preserved).

Goals:
- Capture explicit org-level config customizations in the canonical
  ReconciliationPolicyProfile location before the legacy
  AutoMatchConfig.load_config() path is removed (a later step).
- Idempotent: COALESCE-style updates ensure re-running this migration
  doesn't clobber any subsequent operator edits.

NON-GOALS (deliberately deferred):
- Materializing spec defaults for orgs that have NO customizations.
  Those orgs continue to use the legacy spec-default path until the legacy
  loader is removed.
- Backfilling from GLOBAL settings (organization_id IS NULL).  Global rows
  apply to every org and aren't an org-specific override — preserving them
  belongs with the legacy-loader removal step.

Revision ID: 20260515_backfill_automatch_profile
Revises: 20260515_extend_recon_profile
Create Date: 2026-05-15
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_backfill_automatch_profile"
down_revision: str | None = "20260515_extend_recon_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)


# DomainSettings key → ReconciliationPolicyProfile column.  All boolean
# columns are the per-pass kill switches; integer/string columns are the
# tolerance/buffer/account fields.
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


def _parse_setting_value(
    key: str, value_type: str | None, value_text: str | None, value_json: Any
) -> Any:
    """Coerce a DomainSetting row's stored value to its target type.

    Mirrors the resolution semantics in ``app.services.settings_spec.coerce_value``:
    - bool: "true"/"false"/"1"/"0"/"yes"/"no"/"on"/"off" (case-insensitive)
    - int: parse value_text as int
    - str: trim whitespace
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

    # Default: treat as string
    if raw is None:
        return None
    return str(raw).strip() or None


def upgrade() -> None:
    bind = op.get_bind()

    # Find every org that has at least one org-specific banking.automatch_*
    # setting.  Global rows (organization_id IS NULL) are intentionally
    # excluded — they're not org-specific customizations.
    org_rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT organization_id
            FROM domain_settings
            WHERE domain = 'banking'
              AND key LIKE 'automatch\\_%' ESCAPE '\\'
              AND organization_id IS NOT NULL
              AND is_active = TRUE
            """
        )
    ).fetchall()
    org_ids = [row[0] for row in org_rows]

    if not org_ids:
        logger.info("No org-specific banking.automatch_* settings to backfill.")
        return

    logger.info(
        "Backfilling banking.automatch_* settings for %d org(s) into "
        "reconciliation_policy_profile",
        len(org_ids),
    )

    for org_id in org_ids:
        # Collect this org's automatch_* settings.  All rows here are
        # org-specific by construction (the global rows were excluded above).
        rows = bind.execute(
            sa.text(
                """
                SELECT key, value_type, value_text, value_json
                FROM domain_settings
                WHERE domain = 'banking'
                  AND key LIKE 'automatch\\_%' ESCAPE '\\'
                  AND organization_id = :org_id
                  AND is_active = TRUE
                """
            ),
            {"org_id": org_id},
        ).fetchall()

        column_values: dict[str, Any] = {}
        for key, value_type, value_text, value_json in rows:
            column = _KEY_TO_COLUMN.get(key)
            if not column:
                continue
            parsed = _parse_setting_value(key, value_type, value_text, value_json)
            if parsed is None:
                continue
            column_values[column] = parsed

        if not column_values:
            continue

        # Find or create the org's active profile.  If multiple active
        # profiles exist (unusual), the first one returned wins; matches
        # ReconciliationPolicyService.resolve()'s lookup semantics.
        policy_id = bind.execute(
            sa.text(
                """
                SELECT policy_id
                FROM banking.reconciliation_policy_profile
                WHERE organization_id = :org_id
                  AND is_active = TRUE
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"org_id": org_id},
        ).scalar()

        if policy_id is None:
            policy_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO banking.reconciliation_policy_profile
                        (organization_id, name, is_active)
                    VALUES (:org_id, 'default', TRUE)
                    RETURNING policy_id
                    """
                ),
                {"org_id": org_id},
            ).scalar()
            logger.info(
                "Created default reconciliation_policy_profile for org %s "
                "(policy_id=%s)",
                org_id,
                policy_id,
            )

        # Idempotent COALESCE update: only set columns that are currently
        # NULL.  Operator-set values are never clobbered, and re-running the
        # migration after operators tweak the profile is safe.
        set_clauses: list[str] = []
        params: dict[str, Any] = {"policy_id": policy_id}
        for column, value in column_values.items():
            # Column names are safe — sourced from a fixed dict literal, not
            # user input.  Values are parameterised normally.
            placeholder = f"{column}_v"
            set_clauses.append(f"{column} = COALESCE({column}, :{placeholder})")
            params[placeholder] = value

        bind.execute(
            sa.text(
                f"""
                UPDATE banking.reconciliation_policy_profile
                SET {", ".join(set_clauses)}
                WHERE policy_id = :policy_id
                """
            ),
            params,
        )


def downgrade() -> None:
    """Intentionally a no-op.

    The columns themselves are dropped by ``20260515_extend_recon_profile``'s
    downgrade.  Reversing only the backfill would leave the columns in place
    but NULL — operationally indistinguishable from "never backfilled" since
    the legacy DomainSettings path is still active.  Anyone wanting a true
    revert should downgrade past the schema migration too.
    """
    return
