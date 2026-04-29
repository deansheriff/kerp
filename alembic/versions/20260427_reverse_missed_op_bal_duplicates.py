"""Reverse opening-balance duplicates missed by REV-SYNC-OB-001.

The earlier ``REV-SYNC-OB-001`` (2026-03-12) reversed 16 sync-OB journals in
the range JE-2025-00017–00080 that duplicated balances already posted in
``OB-000001`` (the authoritative 2024 audited TB carry-forward).

A re-scan surfaces two more opening-balance duplicates *outside* that
range that were not addressed:

  * ``JE-2025-00015`` (OP BAL 4) — UBA Bank opening NGN 2,487,543.70
    Same balance is in OB-000001.
  * ``JE-2025-00016`` (OP BAL 5) — Paystack OPEX opening NGN 40,615.65
    Same balance is in OB-000001.

These are reversed here using the same approach (CR the asset, DR Retained
Earnings) so OB-000001 remains the single source of truth for opening
balances.

Notes on items deliberately NOT reversed:

  * ``JE-2025-00012``, ``JE-2025-00013``, ``JE-2025-00014`` (OP BAL 1, 2, 3)
    record opening balances for Zenith 523, Zenith 461, Zenith 454 — none
    of these accounts appear in OB-000001, so they are the *only* source
    of those opening balances and must be retained.
  * ``JE-2025-40488 vs JE-2025-40582`` (Subscription & Renewal NGN 135,000
    on 2025-07-02) is a potential mid-year duplicate where the same
    expense was apparently recorded both via direct bank payment (gl)
    and via supplier invoice (ap). Direction unclear without supplier
    payment history; flagged for finance review rather than auto-reversed.

Revision ID: 20260427_reverse_missed_op_bal
Revises: 20260427_flatten_fixed_asset_categories
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op


revision = "20260427_reverse_missed_op_bal"
down_revision = "20260427_flatten_fixed_asset_categories"
branch_labels = None
depends_on = None


ORG_ID = "00000000-0000-0000-0000-000000000001"
JOURNAL_NUMBER = "REV-MISSED-OB-001"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            v_org UUID := '{ORG_ID}'::uuid;
            v_journal UUID := gen_random_uuid();
            v_batch UUID := gen_random_uuid();
            v_year UUID;
            v_period UUID;
            v_acc_1202 UUID;
            v_acc_1211 UUID;
            v_acc_3100 UUID;
            v_recon_date DATE := DATE '2026-04-27';
            v_now TIMESTAMPTZ := now();
        BEGIN
            IF EXISTS (
                SELECT 1 FROM gl.journal_entry
                WHERE organization_id = v_org
                  AND journal_number = '{JOURNAL_NUMBER}'
            ) THEN
                RETURN;
            END IF;

            SELECT account_id INTO v_acc_1202 FROM gl.account
            WHERE organization_id = v_org AND account_code = '1202';
            SELECT account_id INTO v_acc_1211 FROM gl.account
            WHERE organization_id = v_org AND account_code = '1211';
            SELECT account_id INTO v_acc_3100 FROM gl.account
            WHERE organization_id = v_org AND account_code = '3100';

            -- Tenant-specific reconciliation: skip on blank CI/demo databases
            -- that do not have the production chart of accounts.
            IF v_acc_1202 IS NULL
               OR v_acc_1211 IS NULL
               OR v_acc_3100 IS NULL THEN
                RETURN;
            END IF;

            -- Use the fiscal period that contains the reversal date. If none
            -- exists yet, provision a dedicated adjustment period under FY2026
            -- so this targeted data-fix remains runnable on fresh databases.
            SELECT fiscal_period_id, fiscal_year_id
              INTO v_period, v_year
            FROM gl.fiscal_period
            WHERE organization_id = v_org
              AND start_date <= v_recon_date
              AND end_date >= v_recon_date
            ORDER BY
                CASE WHEN status IN ('OPEN', 'REOPENED') THEN 0 ELSE 1 END,
                start_date DESC
            LIMIT 1;

            IF v_year IS NULL THEN
                SELECT fiscal_year_id
                  INTO v_year
                FROM gl.fiscal_year
                WHERE organization_id = v_org
                  AND start_date <= v_recon_date
                  AND end_date >= v_recon_date
                ORDER BY start_date DESC
                LIMIT 1;
            END IF;

            IF v_year IS NULL THEN
                INSERT INTO gl.fiscal_year (
                    fiscal_year_id, organization_id, year_code, year_name,
                    start_date, end_date, is_adjustment_year, is_closed, created_at
                )
                VALUES (
                    gen_random_uuid(), v_org, 'FY2026', 'FY 2026',
                    DATE '2026-01-01', DATE '2026-12-31', false, false, v_now
                )
                ON CONFLICT (organization_id, year_code) DO NOTHING;

                SELECT fiscal_year_id
                  INTO v_year
                FROM gl.fiscal_year
                WHERE organization_id = v_org
                  AND year_code = 'FY2026';
            END IF;

            IF v_period IS NULL THEN
                INSERT INTO gl.fiscal_period (
                    fiscal_period_id, organization_id, fiscal_year_id,
                    period_number, period_name,
                    start_date, end_date,
                    is_adjustment_period, is_closing_period,
                    status, reopen_count, created_at
                )
                VALUES (
                    gen_random_uuid(), v_org, v_year,
                    (
                        SELECT COALESCE(MAX(period_number), 0) + 1
                        FROM gl.fiscal_period
                        WHERE fiscal_year_id = v_year
                    ),
                    'Reverse Missed OB Duplicates Apr 2026',
                    v_recon_date, v_recon_date,
                    true, false,
                    'OPEN'::period_status, 0, v_now
                );

                SELECT fiscal_period_id
                  INTO v_period
                FROM gl.fiscal_period
                WHERE organization_id = v_org
                  AND fiscal_year_id = v_year
                  AND start_date = v_recon_date
                  AND end_date = v_recon_date
                  AND is_adjustment_period = true
                ORDER BY created_at DESC
                LIMIT 1;
            END IF;

            IF v_period IS NULL THEN
                RAISE EXCEPTION
                    'Unable to resolve or create fiscal period for missed opening-balance reversal on % (org=%)',
                    v_recon_date,
                    v_org;
            END IF;

            INSERT INTO gl.posting_batch (
                batch_id, organization_id, fiscal_period_id,
                idempotency_key, source_module, batch_description,
                total_entries, posted_entries, failed_entries,
                status, submitted_at, submitted_by_user_id,
                processing_started_at, completed_at
            ) VALUES (
                v_batch, v_org, v_period,
                'REV-MISSED-OB-001-' || extract(epoch FROM v_now)::text,
                'GL', 'Reverse missed opening-balance duplicates JE-2025-00015, 00016',
                1, 1, 0, 'POSTED', v_now, v_org, v_now, v_now
            );

            INSERT INTO gl.journal_entry (
                journal_entry_id, organization_id, journal_number,
                journal_type, entry_date, posting_date, fiscal_period_id,
                description, currency_code, exchange_rate,
                total_debit, total_credit,
                total_debit_functional, total_credit_functional,
                status, posting_batch_id, is_reversal, is_intercompany,
                source_module, source_document_type,
                created_by_user_id, posted_by_user_id, posted_at, created_at, version
            ) VALUES (
                v_journal, v_org, '{JOURNAL_NUMBER}',
                'ADJUSTMENT'::journal_type, '2026-04-27', '2026-04-27', v_period,
                'Reverse opening-balance duplicates not covered by REV-SYNC-OB-001: '
                'JE-2025-00015 (UBA NGN 2,487,543.70) and JE-2025-00016 '
                '(Paystack OPEX NGN 40,615.65). Both duplicate balances already in '
                'OB-000001 (authoritative 2024 audited TB carry-forward).',
                'NGN', 1.0,
                2528159.35, 2528159.35,
                2528159.35, 2528159.35,
                'POSTED', v_batch, false, false,
                'GL', 'RECLASS',
                v_org, v_org, v_now, v_now, 1
            );

            INSERT INTO gl.journal_entry_line (
                line_id, journal_entry_id, line_number, account_id, description,
                debit_amount, credit_amount, debit_amount_functional,
                credit_amount_functional, currency_code, exchange_rate, created_at
            ) VALUES
                (gen_random_uuid(), v_journal, 1, v_acc_1202,
                 'Reverse JE-2025-00015 (OP BAL 4) — UBA opening duplicate of OB-000001',
                 0, 2487543.70, 0, 2487543.70, 'NGN', 1.0, v_now),
                (gen_random_uuid(), v_journal, 2, v_acc_1211,
                 'Reverse JE-2025-00016 (OP BAL 5) — Paystack OPEX opening duplicate of OB-000001',
                 0, 40615.65, 0, 40615.65, 'NGN', 1.0, v_now),
                (gen_random_uuid(), v_journal, 3, v_acc_3100,
                 'Reduce Retained Earnings — undo equity overstatement from the two duplicate openings',
                 2528159.35, 0, 2528159.35, 0, 'NGN', 1.0, v_now);

            INSERT INTO gl.posted_ledger_line (
                ledger_line_id, posting_year, organization_id,
                journal_entry_id, journal_line_id, posting_batch_id,
                fiscal_period_id, account_id, account_code,
                entry_date, posting_date, description,
                debit_amount, credit_amount,
                source_module, source_document_type,
                posted_at, posted_by_user_id
            )
            SELECT
                gen_random_uuid(), 2026, v_org,
                v_journal, jel.line_id, v_batch,
                v_period, jel.account_id, a.account_code,
                '2026-04-27'::date, '2026-04-27'::date, jel.description,
                jel.debit_amount, jel.credit_amount,
                'GL', 'RECLASS',
                v_now, v_org
            FROM gl.journal_entry_line jel
            JOIN gl.account a ON a.account_id = jel.account_id
            WHERE jel.journal_entry_id = v_journal;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            v_org UUID := '{ORG_ID}'::uuid;
            v_journal UUID;
            v_batch UUID;
        BEGIN
            SELECT journal_entry_id, posting_batch_id
              INTO v_journal, v_batch
            FROM gl.journal_entry
            WHERE organization_id = v_org AND journal_number = '{JOURNAL_NUMBER}';

            IF v_journal IS NULL THEN
                RETURN;
            END IF;

            DELETE FROM gl.posted_ledger_line WHERE journal_entry_id = v_journal;
            DELETE FROM gl.journal_entry_line WHERE journal_entry_id = v_journal;
            DELETE FROM gl.journal_entry WHERE journal_entry_id = v_journal;
            DELETE FROM gl.posting_batch WHERE batch_id = v_batch;
        END $$;
        """
    )
