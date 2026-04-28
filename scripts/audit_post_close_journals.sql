-- audit_post_close_journals.sql
--
-- Cross-period integrity sweep: detect journals that were written into a
-- closed period AFTER that period's close timestamp. Any such journal is
-- evidence that the period_guard was bypassed — either by direct SQL,
-- a bug in the guard, or a service path that doesn't call require_open_period.
--
-- This is a READ-ONLY diagnostic. It writes nothing.
--
-- Run with NOTICE-level output so the section banners are visible:
--     psql "$DOTMAC_ERP_DB_DSN" -f scripts/audit_post_close_journals.sql
--
-- Sections:
--   1. Summary     — suspect journal counts by period, status, source_module
--   2. Hot periods — periods with the most post-close activity
--   3. Detail      — top 200 worst offenders with everything needed to investigate
--   4. By creator  — which users created the most post-close journals
--   5. SOFT_CLOSED variant — same checks for SOFT_CLOSED periods
--
-- A clean system returns zero rows from sections 1–4 against HARD_CLOSED
-- and ideally near-zero from section 5 (some legitimate adjustments to
-- soft-closed periods are expected via the reopen flow).

\timing on
\pset pager off

\echo
\echo ============================================================
\echo  SECTION 1 — Summary: suspect journals per HARD_CLOSED period
\echo ============================================================
SELECT
    fy.year_code                                 AS fy,
    fp.period_name                               AS period,
    fp.hard_closed_at::date                      AS closed_on,
    COUNT(*)                                       AS suspect_journals,
    COUNT(*) FILTER (WHERE je.status = 'POSTED')   AS posted,
    COUNT(*) FILTER (WHERE je.status = 'APPROVED') AS approved_unposted,
    COUNT(*) FILTER (WHERE je.status = 'SUBMITTED') AS submitted,
    COUNT(*) FILTER (WHERE je.status = 'DRAFT')    AS draft,
    COUNT(*) FILTER (WHERE je.status = 'VOID')     AS void,
    COUNT(*) FILTER (WHERE je.status = 'REVERSED') AS reversed,
    COUNT(DISTINCT je.source_module)               AS distinct_sources,
    COUNT(DISTINCT je.created_by_user_id)          AS distinct_creators
FROM gl.journal_entry je
JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
JOIN gl.fiscal_year fy   ON fy.fiscal_year_id   = fp.fiscal_year_id
WHERE fp.status = 'HARD_CLOSED'
  AND fp.hard_closed_at IS NOT NULL
  AND je.created_at > fp.hard_closed_at
GROUP BY fy.year_code, fp.period_name, fp.hard_closed_at
ORDER BY fy.year_code, fp.period_name;

\echo
\echo ============================================================
\echo  SECTION 2 — Hot periods (top 20 by suspect count)
\echo ============================================================
SELECT
    fy.year_code                       AS fy,
    fp.period_name                     AS period,
    fp.hard_closed_at::date            AS closed_on,
    COUNT(*)                           AS suspect_journals,
    SUM(je.total_debit_functional)     AS total_debit_functional,
    MIN(je.created_at)::date           AS earliest_post_close_create,
    MAX(je.created_at)::date           AS latest_post_close_create
FROM gl.journal_entry je
JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
JOIN gl.fiscal_year fy   ON fy.fiscal_year_id   = fp.fiscal_year_id
WHERE fp.status = 'HARD_CLOSED'
  AND fp.hard_closed_at IS NOT NULL
  AND je.created_at > fp.hard_closed_at
GROUP BY fy.year_code, fp.period_name, fp.hard_closed_at
ORDER BY COUNT(*) DESC
LIMIT 20;

\echo
\echo ============================================================
\echo  SECTION 3 — Detail: top 200 worst offenders
\echo ============================================================
SELECT
    fy.year_code                                       AS fy,
    fp.period_name                                     AS period,
    fp.hard_closed_at::date                            AS closed_on,
    je.journal_number                                  AS journal,
    je.posting_date                                    AS posting_date,
    je.created_at                                      AS created_at,
    EXTRACT(DAY FROM (je.created_at - fp.hard_closed_at))::int AS days_after_close,
    je.status                                          AS status,
    COALESCE(je.source_module, '(none)')               AS source_module,
    COALESCE(je.source_document_type, '(none)')        AS source_doc_type,
    je.created_by_user_id                              AS created_by,
    je.total_debit_functional                          AS amount,
    LEFT(je.description, 80)                           AS description_excerpt
FROM gl.journal_entry je
JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
JOIN gl.fiscal_year fy   ON fy.fiscal_year_id   = fp.fiscal_year_id
WHERE fp.status = 'HARD_CLOSED'
  AND fp.hard_closed_at IS NOT NULL
  AND je.created_at > fp.hard_closed_at
ORDER BY (je.created_at - fp.hard_closed_at) DESC, fp.period_name, je.journal_number
LIMIT 200;

\echo
\echo ============================================================
\echo  SECTION 4 — Creators ranked by post-close journal count
\echo ============================================================
SELECT
    je.created_by_user_id           AS user_id,
    COUNT(*)                        AS suspect_journals,
    COUNT(DISTINCT fp.fiscal_period_id) AS distinct_periods,
    COUNT(DISTINCT je.source_module)    AS distinct_sources,
    MIN(je.created_at)::date            AS first_post_close,
    MAX(je.created_at)::date            AS last_post_close,
    SUM(je.total_debit_functional)      AS total_amount
FROM gl.journal_entry je
JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
WHERE fp.status = 'HARD_CLOSED'
  AND fp.hard_closed_at IS NOT NULL
  AND je.created_at > fp.hard_closed_at
GROUP BY je.created_by_user_id
ORDER BY COUNT(*) DESC
LIMIT 50;

\echo
\echo ============================================================
\echo  SECTION 5 — Same checks for SOFT_CLOSED periods
\echo ============================================================
\echo  (some volume here is normal — soft-close allows controlled re-entry
\echo   via the reopen flow. Investigate spikes, not the baseline.)
\echo
SELECT
    fy.year_code                                       AS fy,
    fp.period_name                                     AS period,
    fp.soft_closed_at::date                            AS closed_on,
    COUNT(*)                                           AS suspect_journals,
    COUNT(*) FILTER (WHERE je.status = 'POSTED')       AS posted,
    COUNT(*) FILTER (WHERE je.status = 'APPROVED')     AS approved_unposted,
    COUNT(*) FILTER (WHERE je.status = 'SUBMITTED')    AS submitted,
    COUNT(*) FILTER (WHERE je.status = 'DRAFT')        AS draft
FROM gl.journal_entry je
JOIN gl.fiscal_period fp ON fp.fiscal_period_id = je.fiscal_period_id
JOIN gl.fiscal_year fy   ON fy.fiscal_year_id   = fp.fiscal_year_id
WHERE fp.status = 'SOFT_CLOSED'
  AND fp.soft_closed_at IS NOT NULL
  AND je.created_at > fp.soft_closed_at
GROUP BY fy.year_code, fp.period_name, fp.soft_closed_at
ORDER BY COUNT(*) DESC, fy.year_code, fp.period_name
LIMIT 50;

\echo
\echo ============================================================
\echo  Done. If sections 1–4 returned zero rows, the period_guard
\echo  has held for HARD_CLOSED periods. Any non-zero section 1–4
\echo  result is a control-bypass signal worth investigating before
\echo  audit fieldwork begins.
\echo ============================================================
