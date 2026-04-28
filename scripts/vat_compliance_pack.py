"""Generate the FY VAT compliance pack — monthly schedule + supporting cuts.

Produces 4 CSVs that finance lays alongside actual FIRS filings to surface
variances:

* ``vat_monthly_schedule_<year>.csv`` — Form-002-shaped monthly schedule
  with three blank columns (filed_net_position, paid_to_firs,
  variance_explanation) for finance to fill in.
* ``exempt_customers_<year>.csv`` — customers issued zero-VAT invoices,
  flagging which are not yet marked ``is_vat_exempt`` in the system.
* ``top_customers_vat_<year>.csv`` — top 50 customers by gross sales with
  output VAT charged.
* ``wht_vat_certificate_inventory_<year>.csv`` — Form A inventory: which
  customers withheld VAT and how much, traced via the GL 4031 account
  back to the originating customer payment.

Why the schedule pulls from invoice tables (not GL):
    GL net positions reflect classification (correct or otherwise). Invoice
    tables are the underlying transactional truth. Comparing GL to filings
    couples two unknowns; comparing invoices-derived schedule to filings
    isolates the question of "did the right amount get reported".

Usage:
    poetry run python scripts/vat_compliance_pack.py --year 2025
    poetry run python scripts/vat_compliance_pack.py --year 2025 \\
        --output-dir /tmp/vat-pack \\
        --org-id 00000000-0000-0000-0000-000000000001
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

MONTHLY_SCHEDULE_SQL = """
WITH ar_monthly AS (
    SELECT
        to_char(i.invoice_date, 'YYYY-MM') AS period,
        SUM(CASE WHEN COALESCE(i.tax_amount, 0) > 0
                 THEN i.total_amount - i.tax_amount ELSE 0 END) AS vatable_subtotal,
        SUM(CASE WHEN COALESCE(i.tax_amount, 0) = 0
                 THEN i.total_amount ELSE 0 END) AS exempt_subtotal,
        SUM(COALESCE(i.tax_amount, 0)) AS output_vat,
        COUNT(*) AS invoice_count
    FROM ar.invoice i
    WHERE i.invoice_date BETWEEN %(start)s AND %(end)s
      AND i.status::text NOT IN ('VOID', 'DRAFT')
      AND i.invoice_type::text != 'CREDIT_NOTE'
    GROUP BY 1
),
ar_credit_notes AS (
    SELECT
        to_char(i.invoice_date, 'YYYY-MM') AS period,
        SUM(COALESCE(i.tax_amount, 0)) AS output_vat_reversed,
        COUNT(*) AS credit_note_count
    FROM ar.invoice i
    WHERE i.invoice_date BETWEEN %(start)s AND %(end)s
      AND i.status::text NOT IN ('VOID', 'DRAFT')
      AND i.invoice_type::text = 'CREDIT_NOTE'
    GROUP BY 1
),
ap_monthly AS (
    SELECT
        to_char(si.invoice_date, 'YYYY-MM') AS period,
        SUM(COALESCE(si.tax_amount, 0)) AS input_vat,
        COUNT(*) AS supplier_invoice_count
    FROM ap.supplier_invoice si
    WHERE si.invoice_date BETWEEN %(start)s AND %(end)s
      AND si.status::text NOT IN ('VOID', 'DRAFT')
    GROUP BY 1
),
wht_vat_monthly AS (
    SELECT
        to_char(pll.posting_date, 'YYYY-MM') AS period,
        SUM(pll.debit_amount - pll.credit_amount) AS wht_vat
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    WHERE pll.posting_date BETWEEN %(start)s AND %(end)s
      AND a.account_code = '4031'
    GROUP BY 1
)
SELECT
    ar.period,
    ar.invoice_count AS sales_invoice_count,
    ROUND(ar.vatable_subtotal, 2) AS vatable_sales_subtotal,
    ROUND(ar.exempt_subtotal, 2) AS exempt_sales,
    ROUND(ar.output_vat, 2) AS output_vat_charged,
    COALESCE(cn.credit_note_count, 0) AS credit_note_count,
    ROUND(COALESCE(cn.output_vat_reversed, 0), 2) AS output_vat_on_credit_notes,
    ROUND(ar.output_vat - COALESCE(cn.output_vat_reversed, 0), 2) AS net_output_vat,
    COALESCE(ap.supplier_invoice_count, 0) AS supplier_invoice_count,
    ROUND(COALESCE(ap.input_vat, 0), 2) AS input_vat_recoverable,
    ROUND(COALESCE(wht.wht_vat, 0), 2) AS wht_vat_credits_form_a,
    ROUND(
        ar.output_vat
        - COALESCE(cn.output_vat_reversed, 0)
        - COALESCE(ap.input_vat, 0)
        - COALESCE(wht.wht_vat, 0),
        2) AS computed_net_payable,
    '' AS filed_net_position,
    '' AS paid_to_firs,
    '' AS variance_explanation
FROM ar_monthly ar
LEFT JOIN ar_credit_notes cn ON cn.period = ar.period
LEFT JOIN ap_monthly ap ON ap.period = ar.period
LEFT JOIN wht_vat_monthly wht ON wht.period = ar.period
ORDER BY ar.period
"""

EXEMPT_CUSTOMERS_SQL = """
SELECT
    c.legal_name AS customer_name,
    c.tax_identification_number AS tin,
    COUNT(*) AS exempt_invoice_count,
    ROUND(SUM(i.total_amount), 2) AS total_exempt_revenue,
    c.is_vat_exempt AS flagged_exempt_in_system
FROM ar.invoice i
JOIN ar.customer c ON c.customer_id = i.customer_id
WHERE i.invoice_date BETWEEN %(start)s AND %(end)s
  AND i.status::text NOT IN ('VOID', 'DRAFT')
  AND i.invoice_type::text != 'CREDIT_NOTE'
  AND COALESCE(i.tax_amount, 0) = 0
GROUP BY c.legal_name, c.tax_identification_number, c.is_vat_exempt
HAVING SUM(i.total_amount) > 0
ORDER BY SUM(i.total_amount) DESC
"""

TOP_CUSTOMERS_SQL = """
SELECT
    c.legal_name AS customer_name,
    c.tax_identification_number AS tin,
    COUNT(*) AS invoice_count,
    ROUND(SUM(i.total_amount - COALESCE(i.tax_amount, 0)), 2) AS net_subtotal,
    ROUND(SUM(COALESCE(i.tax_amount, 0)), 2) AS output_vat,
    ROUND(SUM(i.total_amount), 2) AS gross
FROM ar.invoice i
JOIN ar.customer c ON c.customer_id = i.customer_id
WHERE i.invoice_date BETWEEN %(start)s AND %(end)s
  AND i.status::text NOT IN ('VOID', 'DRAFT')
  AND i.invoice_type::text != 'CREDIT_NOTE'
GROUP BY c.legal_name, c.tax_identification_number
ORDER BY SUM(i.total_amount) DESC
LIMIT 50
"""

WHT_INVENTORY_SQL = """
WITH wht_lines AS (
    SELECT
        pll.posting_date,
        pll.journal_entry_id,
        pll.debit_amount AS wht_vat_amount
    FROM gl.posted_ledger_line pll
    JOIN gl.account a ON a.account_id = pll.account_id
    WHERE a.account_code = '4031'
      AND pll.posting_date BETWEEN %(start)s AND %(end)s
      AND pll.debit_amount > 0
)
SELECT
    c.legal_name AS customer_name,
    c.tax_identification_number AS tin,
    COUNT(DISTINCT wht.journal_entry_id) AS certificate_count,
    ROUND(SUM(wht.wht_vat_amount), 2) AS total_vat_withheld,
    to_char(MIN(wht.posting_date), 'YYYY-MM-DD') AS earliest,
    to_char(MAX(wht.posting_date), 'YYYY-MM-DD') AS latest,
    '' AS form_a_certificate_received,
    '' AS form_a_certificate_filed_with_firs
FROM wht_lines wht
JOIN ar.customer_payment cp ON cp.journal_entry_id = wht.journal_entry_id
JOIN ar.customer c ON c.customer_id = cp.customer_id
GROUP BY c.legal_name, c.tax_identification_number
ORDER BY SUM(wht.wht_vat_amount) DESC
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
    params = {"start": period_start, "end": period_end}

    conn = psycopg.connect(args.dsn, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            # SET cannot accept bind params; use set_config() instead.
            cur.execute(
                "SELECT set_config('app.current_organization_id', %s, false)",
                (args.org_id,),
            )
            schedule = args.output_dir / f"vat_monthly_schedule_{args.year}.csv"
            exempt = args.output_dir / f"exempt_customers_{args.year}.csv"
            top = args.output_dir / f"top_customers_vat_{args.year}.csv"
            wht = args.output_dir / f"wht_vat_certificate_inventory_{args.year}.csv"

            n_schedule = _dump_csv(cur, MONTHLY_SCHEDULE_SQL, params, schedule)
            n_exempt = _dump_csv(cur, EXEMPT_CUSTOMERS_SQL, params, exempt)
            n_top = _dump_csv(cur, TOP_CUSTOMERS_SQL, params, top)
            n_wht = _dump_csv(cur, WHT_INVENTORY_SQL, params, wht)
    finally:
        conn.close()

    logger.info("VAT compliance pack for FY%s:", args.year)
    logger.info("  %s — %d months", schedule, n_schedule)
    logger.info("  %s — %d exempt customers", exempt, n_exempt)
    logger.info("  %s — top %d customers", top, n_top)
    logger.info("  %s — %d Form A certificates to chase", wht, n_wht)
    return 0


if __name__ == "__main__":
    sys.exit(main())
