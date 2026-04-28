"""Undo HARD_CLOSED/SOFT_CLOSED 2025 fiscal periods (migration artifact).

Context
-------
During a historical data import in March 2026, all FY2025 monthly periods
were transitioned through SOFT_CLOSED → HARD_CLOSED by the migration
script. This was *not* a genuine accounting close:

  * No FY2025 trial balance was finalized or signed off.
  * No closing journal was posted to zero out P&L into Retained Earnings.
  * No FY2026 opening journal was rolled forward from FY2025 closing
    balances.
  * No external financial statements were issued from the closed state.
  * No auditor, regulator, or board has reviewed FY2025 against the
    closed status.

The closed status is therefore a procedural artifact of the migration
script rather than an audit event that needs reversing with a trail.
This migration reverts those periods to OPEN so the genuine close
(reconciliations + closing journals + FY2026 opening) can proceed.

Safety
------
Reverting a HARD_CLOSED period is a controlled action even when it is
the right thing to do. This migration self-protects: it counts every
downstream artifact that would have been written *because* of the close
(aging snapshots, period-event notifications, post-close journals,
inventory valuations) and aborts loudly if any are found. If the abort
fires, the close is no longer a pure migration artifact and reversal
must go through a proper force-reopen audit-trail flow instead.

Idempotent: re-running after success is a no-op (no rows match the
status filter).

Note on year_code: the ``gl.fiscal_year.year_code`` column changed
convention mid-history. Years 2015–2021 are stored as bare ``'2015'``,
``'2016'``, etc. Years 2022 onward use the ``'FY2022'`` prefix form.
This migration matches both spellings for ``2025`` defensively.

Revision ID: 20260428_undo_2025_period_close_artifact
Revises: 20260427_reverse_missed_op_bal
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op


revision = "20260428_undo_2025_period_close_artifact"
down_revision = "20260427_reverse_missed_op_bal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_period_ids UUID[];
            v_period_count INTEGER;
            v_ar_snapshots INTEGER;
            v_ap_snapshots INTEGER;
            v_inv_valuations INTEGER;
            v_period_notifications INTEGER;
            v_post_close_journals INTEGER;
            v_total_artifacts INTEGER;
            v_period RECORD;
        BEGIN
            -- Step 1: identify affected 2025 periods.
            SELECT array_agg(fp.fiscal_period_id)
              INTO v_period_ids
              FROM gl.fiscal_period fp
              JOIN gl.fiscal_year fy ON fy.fiscal_year_id = fp.fiscal_year_id
             WHERE fy.year_code IN ('FY2025', '2025')
               AND fp.status IN ('HARD_CLOSED', 'SOFT_CLOSED');

            v_period_count := COALESCE(array_length(v_period_ids, 1), 0);

            IF v_period_count = 0 THEN
                RAISE NOTICE 'No 2025 HARD_CLOSED/SOFT_CLOSED periods found. Nothing to undo.';
                RETURN;
            END IF;

            RAISE NOTICE 'Found % closed 2025 periods to revert.', v_period_count;

            -- Step 2: safety check — count downstream artifacts.
            SELECT COUNT(*) INTO v_ar_snapshots
              FROM ar.ar_aging_snapshot
             WHERE fiscal_period_id = ANY(v_period_ids);

            SELECT COUNT(*) INTO v_ap_snapshots
              FROM ap.ap_aging_snapshot
             WHERE fiscal_period_id = ANY(v_period_ids);

            SELECT COUNT(*) INTO v_inv_valuations
              FROM inv.inventory_valuation
             WHERE fiscal_period_id = ANY(v_period_ids);

            SELECT COUNT(*) INTO v_period_notifications
              FROM public.notification
             WHERE entity_type = 'FISCAL_PERIOD'
               AND entity_id = ANY(v_period_ids);

            SELECT COUNT(*) INTO v_post_close_journals
              FROM gl.journal_entry je
              JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
             WHERE fp.fiscal_period_id = ANY(v_period_ids)
               AND fp.hard_closed_at IS NOT NULL
               AND je.created_at > fp.hard_closed_at;

            v_total_artifacts := v_ar_snapshots + v_ap_snapshots
                              + v_inv_valuations + v_period_notifications
                              + v_post_close_journals;

            RAISE NOTICE 'Safety check: ar_snapshots=%, ap_snapshots=%, inv_valuations=%, period_notifications=%, post_close_journals=%',
                v_ar_snapshots, v_ap_snapshots, v_inv_valuations,
                v_period_notifications, v_post_close_journals;

            IF v_total_artifacts > 0 THEN
                RAISE EXCEPTION
                    'Refusing to undo close: % downstream artifacts reference the closed state. '
                    'The close has caused observable effects beyond the period status flag and '
                    'is no longer a pure migration artifact. Use the force-reopen audit-trail '
                    'flow (REOPENED status + reopen_session_id + period_reopen_audit row) instead.',
                    v_total_artifacts;
            END IF;

            -- Step 3: log each period before reverting (for migration audit).
            FOR v_period IN
                SELECT fp.period_name, fp.status, fp.hard_closed_at, fp.soft_closed_at
                  FROM gl.fiscal_period fp
                 WHERE fp.fiscal_period_id = ANY(v_period_ids)
                 ORDER BY fp.start_date
            LOOP
                RAISE NOTICE '  Reverting % (status=%, hard_closed_at=%, soft_closed_at=%) -> OPEN',
                    v_period.period_name, v_period.status,
                    v_period.hard_closed_at, v_period.soft_closed_at;
            END LOOP;

            -- Step 4: revert status and clear close metadata.
            UPDATE gl.fiscal_period
               SET status = 'OPEN',
                   hard_closed_at = NULL,
                   hard_closed_by_user_id = NULL,
                   soft_closed_at = NULL,
                   soft_closed_by_user_id = NULL
             WHERE fiscal_period_id = ANY(v_period_ids);

            RAISE NOTICE 'Reverted % fiscal periods to OPEN.', v_period_count;
        END $$;
        """
    )


def downgrade() -> None:
    """Best-effort restore of HARD_CLOSED status on 2025 periods.

    The original ``hard_closed_at`` / ``hard_closed_by_user_id`` /
    ``soft_closed_at`` / ``soft_closed_by_user_id`` values cannot be
    recovered. If a downgrade is genuinely needed, run the proper
    soft-close → hard-close service flow instead so the timestamps and
    user attribution are populated correctly.
    """
    op.execute(
        """
        DO $$
        DECLARE
            v_now TIMESTAMPTZ := now();
            v_count INTEGER;
        BEGIN
            UPDATE gl.fiscal_period fp
               SET status = 'HARD_CLOSED',
                   soft_closed_at = COALESCE(fp.soft_closed_at, v_now),
                   hard_closed_at = COALESCE(fp.hard_closed_at, v_now)
              FROM gl.fiscal_year fy
             WHERE fy.fiscal_year_id = fp.fiscal_year_id
               AND fy.year_code IN ('FY2025', '2025')
               AND fp.status = 'OPEN';

            GET DIAGNOSTICS v_count = ROW_COUNT;
            RAISE NOTICE 'Best-effort downgrade: re-applied HARD_CLOSED to % periods (timestamps NOT restored).', v_count;
        END $$;
        """
    )
