"""Generate the FY WHT compliance pack — both directions of withholding tax.

Nigerian WHT runs in two flows that must be filed and reconciled separately:

  1. **WHT receivable (Form B credits)**: customers withhold tax from our
     payments and remit on our behalf. We collect Form B certificates and
     offset against our annual Companies Income Tax (CIT) bill. GL home:
     account 1420 ``Withholding Taxes`` (asset).

  2. **WHT payable (Form A monthly remittance)**: we withhold tax from
     supplier payments and remit to FIRS within 21 days of deduction. GL
     home: account 2110 ``WHT`` (liability).

The pack produces five CSVs:

  * ``wht_monthly_schedule_<year>.csv`` — month-by-month accumulation in
     both directions, with three blank columns for finance to record what
     was actually filed and remitted.
  * ``wht_form_b_inventory_<year>.csv`` — every customer payment with WHT
     deducted (Form B inventory we recoup against CIT).
  * ``wht_form_a_remittance_inventory_<year>.csv`` — every supplier
     transaction where we withheld (the basis for Form A monthly returns).
  * ``wht_top_withholding_customers_<year>.csv`` — top customers by WHT
     deducted from us (focus list for Form B chase).
  * ``wht_anomalies_<year>.csv`` — duplicate opening-balance entries and
     other red flags found by automated checks.

A material flag the pack will surface: the FY2025 dev DB has the
``WHT receivable`` opening balance posted **twice** (once via
``IMPORT.OPENING_BALANCE``, once via a ``gl.JOURNAL`` referenced
"WHT-OPENING BAL"), inflating account 1420 by ~₦68.31M. The anomalies
CSV calls this out.

Usage:
    poetry run python scripts/wht_compliance_pack.py --year 2025
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Account codes — adjust here if the chart of accounts changes.
WHT_RECEIVABLE_ACCOUNT = "1420"
WHT_PAYABLE_ACCOUNT = "2110"
STAMP_DUTY_ACCOUNT = "4030"

MONTHLY_SCHEDULE_SQL = """
WITH wht_recv AS (
    SELECT
        to_char(pll.posting_date, 'YYYY-MM') AS period,
        SUM(pll.debit_amount) AS recv_dr,
        SUM(pll.credit_amount) AS recv_cr
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    WHERE a.account_code = %(wht_recv)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
    GROUP BY 1
),
wht_pay AS (
    SELECT
        to_char(pll.posting_date, 'YYYY-MM') AS period,
        SUM(pll.credit_amount) AS pay_cr,
        SUM(pll.debit_amount) AS pay_dr
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    WHERE a.account_code = %(wht_pay)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
    GROUP BY 1
),
stamp AS (
    SELECT
        to_char(pll.posting_date, 'YYYY-MM') AS period,
        SUM(pll.debit_amount) AS stamp_dr
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    WHERE a.account_code = %(stamp)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
    GROUP BY 1
),
all_periods AS (
    SELECT period FROM wht_recv
    UNION SELECT period FROM wht_pay
    UNION SELECT period FROM stamp
)
SELECT
    p.period,
    ROUND(COALESCE(r.recv_dr, 0), 2) AS wht_received_from_customers,
    ROUND(COALESCE(r.recv_cr, 0), 2) AS wht_recv_credits_used,
    ROUND(COALESCE(pp.pay_cr, 0), 2) AS wht_deducted_from_suppliers,
    ROUND(COALESCE(pp.pay_dr, 0), 2) AS wht_remitted_to_firs,
    ROUND(COALESCE(s.stamp_dr, 0), 2) AS stamp_duty_deducted,
    '' AS form_b_certs_received,
    '' AS form_a_returns_filed,
    '' AS variance_explanation
FROM all_periods p
LEFT JOIN wht_recv r ON r.period = p.period
LEFT JOIN wht_pay pp ON pp.period = p.period
LEFT JOIN stamp s ON s.period = p.period
ORDER BY p.period
"""

FORM_B_INVENTORY_SQL = """
WITH wht_lines AS (
    SELECT
        pll.posting_date,
        pll.journal_entry_id,
        pll.debit_amount AS wht_amount
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    JOIN gl.journal_entry je ON je.journal_entry_id = pll.journal_entry_id
    WHERE a.account_code = %(wht_recv)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
      AND pll.debit_amount > 0
      AND LOWER(je.source_module) = 'ar'
      AND je.source_document_type = 'CUSTOMER_PAYMENT'
)
SELECT
    to_char(wht.posting_date, 'YYYY-MM-DD') AS payment_date,
    cp.payment_number,
    c.legal_name AS customer_name,
    c.tax_identification_number AS customer_tin,
    ROUND(wht.wht_amount, 2) AS wht_amount,
    ROUND(cp.amount, 2) AS net_payment_received,
    ROUND(cp.amount + wht.wht_amount, 2) AS approx_gross_invoice,
    '' AS form_b_certificate_received,
    '' AS form_b_filed_with_cit_return
FROM wht_lines wht
JOIN ar.customer_payment cp ON cp.journal_entry_id = wht.journal_entry_id
JOIN ar.customer c ON c.customer_id = cp.customer_id
ORDER BY wht.posting_date, c.legal_name
"""

TOP_WITHHOLDING_CUSTOMERS_SQL = """
WITH wht_lines AS (
    SELECT pll.journal_entry_id, pll.debit_amount AS wht_amount
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    JOIN gl.journal_entry je ON je.journal_entry_id = pll.journal_entry_id
    WHERE a.account_code = %(wht_recv)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
      AND pll.debit_amount > 0
      AND LOWER(je.source_module) = 'ar'
      AND je.source_document_type = 'CUSTOMER_PAYMENT'
)
SELECT
    c.legal_name AS customer_name,
    c.tax_identification_number AS tin,
    COUNT(DISTINCT wht.journal_entry_id) AS payment_count,
    ROUND(SUM(wht.wht_amount), 2) AS total_wht_deducted
FROM wht_lines wht
JOIN ar.customer_payment cp ON cp.journal_entry_id = wht.journal_entry_id
JOIN ar.customer c ON c.customer_id = cp.customer_id
GROUP BY c.legal_name, c.tax_identification_number
ORDER BY SUM(wht.wht_amount) DESC
"""

FORM_A_REMITTANCE_INVENTORY_SQL = """
WITH wht_lines AS (
    SELECT
        pll.posting_date,
        pll.journal_entry_id,
        pll.credit_amount AS wht_amount,
        je.source_module,
        je.source_document_type
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    JOIN gl.journal_entry je ON je.journal_entry_id = pll.journal_entry_id
    WHERE a.account_code = %(wht_pay)s
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
      AND pll.credit_amount > 0
      AND LOWER(je.source_module) IN ('ap', 'expense')
)
SELECT
    to_char(wht.posting_date, 'YYYY-MM-DD') AS deduction_date,
    je.journal_number,
    wht.source_module,
    wht.source_document_type,
    ROUND(wht.wht_amount, 2) AS wht_withheld,
    je.description
FROM wht_lines wht
JOIN gl.journal_entry je ON je.journal_entry_id = wht.journal_entry_id
ORDER BY wht.posting_date
"""

ANOMALIES_SQL = """
-- Duplicate opening-balance entries on WHT accounts: same date, similar amount, different journal
SELECT
    'DUPLICATE_OPENING_BALANCE' AS anomaly,
    a.account_code,
    a.account_name,
    je1.journal_number AS journal_a,
    je1.source_module AS journal_a_source,
    je2.journal_number AS journal_b,
    je2.source_module AS journal_b_source,
    ROUND(jel1.debit_amount_functional, 2) AS amount_a,
    ROUND(jel2.debit_amount_functional, 2) AS amount_b,
    je1.entry_date,
    je1.description AS journal_a_desc,
    je2.description AS journal_b_desc
FROM gl.journal_entry je1
JOIN gl.journal_entry_line jel1 ON jel1.journal_entry_id = je1.journal_entry_id
JOIN gl.account a ON a.account_id = jel1.account_id
JOIN gl.journal_entry je2 ON je2.entry_date = je1.entry_date
                          AND je2.journal_entry_id < je1.journal_entry_id
JOIN gl.journal_entry_line jel2 ON jel2.journal_entry_id = je2.journal_entry_id
                                AND jel2.account_id = jel1.account_id
WHERE a.account_code IN (%(wht_recv)s, %(wht_pay)s)
  AND ABS(jel1.debit_amount_functional - jel2.debit_amount_functional) < 1.0
  AND jel1.debit_amount_functional > 1000000
  AND je1.entry_date BETWEEN %(start)s AND %(end)s
  AND (je1.source_module IN ('IMPORT', 'gl') OR je2.source_module IN ('IMPORT', 'gl'))
"""


def _dump_csv(cursor: psycopg.Cursor, sql: str, params: dict, path: Path) -> int:
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if not rows:
        path.write_text("")
        return 0
    columns = [col.name for col in cursor.description or []]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    parser.add_argument("--org-id", default=DEFAULT_ORG_ID)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DOTMAC_ERP_DB_DSN")
        or "postgresql://claude_readonly:claude_readonly@localhost:5437/dotmac_erp",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    period_start = f"{args.year}-01-01"
    period_end = f"{args.year}-12-31"
    params = {
        "start": period_start,
        "end": period_end,
        "wht_recv": WHT_RECEIVABLE_ACCOUNT,
        "wht_pay": WHT_PAYABLE_ACCOUNT,
        "stamp": STAMP_DUTY_ACCOUNT,
    }

    conn = psycopg.connect(args.dsn, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_organization_id', %s, false)",
                (args.org_id,),
            )

            schedule = args.output_dir / f"wht_monthly_schedule_{args.year}.csv"
            form_b = args.output_dir / f"wht_form_b_inventory_{args.year}.csv"
            top = args.output_dir / f"wht_top_withholding_customers_{args.year}.csv"
            form_a = (
                args.output_dir / f"wht_form_a_remittance_inventory_{args.year}.csv"
            )
            anomalies = args.output_dir / f"wht_anomalies_{args.year}.csv"

            n_schedule = _dump_csv(cur, MONTHLY_SCHEDULE_SQL, params, schedule)
            n_form_b = _dump_csv(cur, FORM_B_INVENTORY_SQL, params, form_b)
            n_top = _dump_csv(cur, TOP_WITHHOLDING_CUSTOMERS_SQL, params, top)
            n_form_a = _dump_csv(cur, FORM_A_REMITTANCE_INVENTORY_SQL, params, form_a)
            n_anomalies = _dump_csv(cur, ANOMALIES_SQL, params, anomalies)
    finally:
        conn.close()

    logger.info("WHT compliance pack for FY%s:", args.year)
    logger.info("  %s — %d months", schedule, n_schedule)
    logger.info("  %s — %d Form B credits to recoup against CIT", form_b, n_form_b)
    logger.info("  %s — top %d withholding customers", top, n_top)
    logger.info("  %s — %d Form A remittance lines (we owe FIRS)", form_a, n_form_a)
    logger.info("  %s — %d anomalies flagged", anomalies, n_anomalies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
