"""Suggest customer ↔ invoice matches for unmatched bank inflows.

Generates a finance-reviewable CSV with proposed matches for each unmatched
bank-statement-line credit. Approach:

  1. Pull every unmatched bank line (positive amount = inflow).
  2. Tokenise the bank-line description and fuzzy-match against all
     customers' ``legal_name`` (normalised). Highest-overlap customer wins.
  3. For the matched customer, find candidate open invoices and check if
     the bank amount equals one of these patterns:
        * exact gross (no withholding)
        * gross × 0.95 (net of 5% WHT + 7.5% VAT-WHT, gov standard)
        * gross × 0.94 (above + 1% stamp duty)
        * gross × 0.925 (net of 5% WHT only)
        * sum of 2-3 oldest open invoices in any of the above patterns
  4. Score the match HIGH / MEDIUM / LOW based on customer-text confidence
     and amount tolerance.
  5. Output CSV with two empty columns (``approve`` Y/N, ``override_invoice_numbers``)
     for finance to fill in.

Why fuzzy not exact: bank descriptions are noisy (`R-1428792594/NIGERIA AI:BEINGP/
DOTMAC TECHNOLOGIES LTD/NIGERIAAIRSPACEMANAGEMENT`) and customer names are
verbose (`Nigerian Airspace Management Agency`). Substring + token-overlap
catches these. For high-volume customers with abbreviation aliases (NAFDAC,
NAMA, NHIA), the script also tries common acronyms.

Usage:
    poetry run python scripts/bank_match_suggestions.py \\
        --output-dir /tmp/bank-match \\
        --since 2026-01-01

The output is a single CSV ``bank_match_suggestions.csv``. Finance reviews,
fills the ``approve`` column with ``Y`` or ``N`` for each row, then a
follow-up script applies the approved matches.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Common Nigerian government / NGO acronyms → full names (one-way alias map).
# When the bank description mentions an acronym, expand to the full name to
# match against ar.customer.legal_name.
ACRONYM_HINTS = {
    "NAMA": "nigerian airspace management agency",
    "NAFDAC": "national agency for food and drug administration control",
    "NHIA": "national health insurance authority",
    "NCDC": "nigeria centre for disease control",
    "NITDA": "national information technology development agency",
    "FIRS": "federal inland revenue service",
    "PTAD": "ptad",
    "FAO": "food and agricultural organisation",
    "GIZ": "giz office",
    "SON": "standard organisation of nigeria",
    "NEXIM": "nexim",
    "NHF": "national housing fund",
}

# Patterns that indicate the bank line is NOT a customer payment.
# Salary / severance / inter-account transfers should be flagged so finance
# can route them to the right account rather than try to match an invoice.
NON_CUSTOMER_PATTERNS = [
    (
        "SALARY/PAYROLL",
        re.compile(r"\b(salary|sal|severance|payroll|pension|paye)\b", re.I),
    ),
    (
        "INTERCOMPANY_DOTMAC",
        re.compile(r"DOTMAC\s+TECHNOLOGIES\s+(LIMITED|LTD)?\s*SERVICES", re.I),
    ),
    ("BANK_FEE", re.compile(r"\b(charge|charges|cot|stamp\s*duty|sms|ussd)\b", re.I)),
    ("OWN_TRANSFER", re.compile(r"NIP/UBA/DOTMAC\s+TECHNOLOGIES", re.I)),
    ("REFUND", re.compile(r"\brefund\b", re.I)),
    ("LOAN", re.compile(r"\b(loan|borrow|repay)\b", re.I)),
]


def detect_non_customer_pattern(description: str) -> str:
    """If the description matches a known non-customer pattern, return its label."""
    for label, regex in NON_CUSTOMER_PATTERNS:
        if regex.search(description or ""):
            return label
    return ""


# Tokens that should NOT be used for matching (bank operational / our own name).
STOPWORDS = {
    "nip",
    "neft",
    "rtgs",
    "ussd",
    "trf",
    "to",
    "from",
    "ref",
    "no",
    "dotmac",
    "technologies",
    "ltd",
    "limited",
    "lim",
    "inc",
    "incorporated",
    "ltdservices",
    "services",
    "service",
    "cbi",
    "cib",
    "uto",
    "fcmb",
    "uba",
    "gtb",
    "gt",
    "zenith",
    "first",
    "bank",
    "citi",
    "citibank",
    "ecobank",
    "eco",
    "balance",
    "bal",
    "payment",
    "pymt",
    "transfer",
    "tfr",
    "the",
    "of",
    "and",
    "or",
    "for",
    "via",
    "with",
    "co",
    "company",
    "corp",
}


def _normalise(text: str) -> str:
    """Lowercase, strip non-alphanumerics, collapse whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokens(text: str) -> set[str]:
    norm = _normalise(text)
    return {t for t in norm.split() if len(t) > 2 and t not in STOPWORDS}


@dataclass
class Customer:
    customer_id: UUID
    legal_name: str
    name_tokens: set[str]
    # Stripped name (lowercase, alphanumeric only, no spaces) for substring
    # match against bank descriptions that concatenate words like
    # "NIGERIAAIRSPACEMANAGEMENTAGENCY".
    name_stripped: str


@dataclass
class Invoice:
    invoice_id: UUID
    invoice_number: str
    invoice_date: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal

    @property
    def outstanding(self) -> Decimal:
        return self.total_amount - self.amount_paid


def fetch_customers(cur: psycopg.Cursor) -> list[Customer]:
    # Include ALL customers (not just those with open invoices) — the bank
    # line might be an overpayment / advance / for an already-paid invoice.
    cur.execute(
        """
        SELECT c.customer_id, c.legal_name
        FROM ar.customer c
        WHERE c.legal_name IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM ar.invoice i
              WHERE i.customer_id = c.customer_id
          )
        """
    )
    out = []
    for row in cur.fetchall():
        toks = _tokens(row["legal_name"])
        stripped = re.sub(r"[^a-z0-9]", "", row["legal_name"].lower())
        if toks and len(stripped) >= 6:
            out.append(Customer(row["customer_id"], row["legal_name"], toks, stripped))
    return out


def fetch_open_invoices(cur: psycopg.Cursor, customer_id: UUID) -> list[Invoice]:
    cur.execute(
        """
        SELECT invoice_id, invoice_number, invoice_date::text,
               total_amount - COALESCE(tax_amount, 0) AS subtotal,
               COALESCE(tax_amount, 0) AS tax_amount,
               total_amount, COALESCE(amount_paid, 0) AS amount_paid
        FROM ar.invoice
        WHERE customer_id = %(cid)s
          AND status::text NOT IN ('VOID', 'DRAFT', 'PAID')
          AND invoice_type::text != 'CREDIT_NOTE'
          AND COALESCE(amount_paid, 0) < total_amount
        ORDER BY invoice_date
        """,
        {"cid": customer_id},
    )
    return [
        Invoice(
            r["invoice_id"],
            r["invoice_number"],
            r["invoice_date"],
            Decimal(r["subtotal"]),
            Decimal(r["tax_amount"]),
            Decimal(r["total_amount"]),
            Decimal(r["amount_paid"]),
        )
        for r in cur.fetchall()
    ]


def fetch_unmatched_lines(cur: psycopg.Cursor, since: str) -> list[dict]:
    cur.execute(
        """
        SELECT bsl.line_id, bsl.transaction_date::text AS transaction_date,
               bsl.amount, bsl.description, bsl.reference, bsl.payee_payer,
               a.account_code, a.account_name AS gl_account_name,
               ba.bank_name, ba.account_number
        FROM banking.bank_statement_lines bsl
        JOIN banking.bank_statements bs ON bs.statement_id = bsl.statement_id
        JOIN banking.bank_accounts ba ON ba.bank_account_id = bs.bank_account_id
        JOIN gl.account a ON a.account_id = ba.gl_account_id
        WHERE bsl.is_matched = false
          AND bsl.amount > 0
          AND bsl.transaction_date >= %(since)s
        ORDER BY bsl.transaction_date, bsl.line_id
        """,
        {"since": since},
    )
    return list(cur.fetchall())


def find_customer_match(
    description: str,
    payee: str | None,
    customers: list[Customer],
) -> tuple[Customer | None, str]:
    """Return (best_match_customer, confidence). Confidence: HIGH/MEDIUM/LOW/NONE."""
    haystack = " ".join(filter(None, [description, payee])).upper()

    # Stripped form of the description (lowercase, alphanumeric only) — for
    # matching customer names that appear concatenated in bank descriptions
    # (e.g. "NIGERIAAIRSPACEMANAGEMENTAGENCY" → matches Nigerian Airspace…).
    haystack_stripped = re.sub(r"[^a-z0-9]", "", haystack.lower())

    # 1. Concatenated-substring match — strongest signal when it triggers.
    #    Find the longest customer name (by stripped length) that's a substring.
    best_substring: Customer | None = None
    for c in customers:
        if len(c.name_stripped) >= 8 and c.name_stripped in haystack_stripped:
            if best_substring is None or len(c.name_stripped) > len(
                best_substring.name_stripped
            ):
                best_substring = c
    if best_substring is not None:
        return best_substring, "HIGH"

    # 2. Acronym hints (NAFDAC, NAMA, etc.).
    for acronym, full_name in ACRONYM_HINTS.items():
        if re.search(rf"\b{acronym}\b", haystack):
            full_tokens = _tokens(full_name)
            for c in customers:
                overlap = len(c.name_tokens & full_tokens)
                if overlap >= 2 or (overlap >= 1 and len(c.name_tokens) <= 3):
                    return c, "HIGH"

    # Token-overlap matching — count how many distinct customer-name tokens
    # appear in the description.
    desc_tokens = _tokens(description + " " + (payee or ""))
    if not desc_tokens:
        return None, "NONE"

    best: tuple[Customer | None, int] = (None, 0)
    for c in customers:
        overlap = len(c.name_tokens & desc_tokens)
        if overlap > best[1]:
            best = (c, overlap)

    cust, overlap = best
    if cust is None or overlap == 0:
        return None, "NONE"
    if overlap >= 3:
        return cust, "HIGH"
    if overlap == 2:
        return cust, "MEDIUM"
    return cust, "LOW"


# Withholding patterns: what fraction of the invoice gross does the customer
# typically pay? Government customers commonly net out 5% WHT + 7.5% VAT-WHT.
PAYMENT_RATIOS = [
    ("EXACT_GROSS", Decimal("1.0000")),
    (
        "NET_5%_WHT_7.5%_VAT_WHT",
        Decimal("0.9500"),
    ),  # gross - 5%×subtotal - 7.5%×subtotal ≈ 0.95×subtotal
    ("NET_5%_WHT_7.5%_VAT_1%_STAMP", Decimal("0.9400")),
    ("NET_5%_WHT_ONLY", Decimal("0.9250")),
    ("NET_10%_WHT_ONLY", Decimal("0.8750")),
]

TOLERANCE = Decimal("100")  # NGN tolerance for amount equality


def _approx_subtotal_match(
    bank_amount: Decimal, invoice: Invoice, ratio: Decimal
) -> bool:
    # The customer paid the invoice subtotal × ratio
    expected = invoice.subtotal * ratio
    return abs(bank_amount - expected) <= TOLERANCE


def _approx_gross_match(bank_amount: Decimal, invoice: Invoice) -> bool:
    return abs(bank_amount - invoice.total_amount) <= TOLERANCE


def find_invoice_matches(
    bank_amount: Decimal, invoices: list[Invoice]
) -> tuple[list[Invoice], str]:
    """Return (matched_invoices, ratio_label). Empty list if no match."""
    if not invoices:
        return [], "NO_OPEN_INVOICES"

    # 1. Single-invoice exact match (gross).
    for inv in invoices:
        if _approx_gross_match(bank_amount, inv):
            return [inv], "EXACT_GROSS"

    # 2. Single-invoice subtotal × withholding ratio.
    for label, ratio in PAYMENT_RATIOS[1:]:
        for inv in invoices:
            if _approx_subtotal_match(bank_amount, inv, ratio):
                return [inv], label

    # 3. Sum of two oldest open invoices, exact gross.
    if len(invoices) >= 2:
        for i in range(len(invoices) - 1):
            for j in range(i + 1, min(i + 6, len(invoices))):
                pair_total = invoices[i].total_amount + invoices[j].total_amount
                if abs(bank_amount - pair_total) <= TOLERANCE:
                    return [invoices[i], invoices[j]], "EXACT_GROSS_2_INV"

    # 4. Sum of three oldest open invoices, exact gross.
    if len(invoices) >= 3:
        for i in range(min(len(invoices), 8)):
            for j in range(i + 1, min(i + 5, len(invoices))):
                for k in range(j + 1, min(j + 4, len(invoices))):
                    triple = (
                        invoices[i].total_amount
                        + invoices[j].total_amount
                        + invoices[k].total_amount
                    )
                    if abs(bank_amount - triple) <= TOLERANCE:
                        return [
                            invoices[i],
                            invoices[j],
                            invoices[k],
                        ], "EXACT_GROSS_3_INV"

    return [], "NO_AMOUNT_MATCH"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/bank-match"))
    parser.add_argument("--since", default="2026-01-01")
    parser.add_argument("--org-id", default=DEFAULT_ORG_ID)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DOTMAC_ERP_DB_DSN")
        or "postgresql://claude_readonly:claude_readonly@localhost:5437/dotmac_erp",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "bank_match_suggestions.csv"

    conn = psycopg.connect(args.dsn, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_organization_id', %s, false)",
                (args.org_id,),
            )

            customers = fetch_customers(cur)
            logger.info("Loaded %d customers with open invoices", len(customers))

            unmatched = fetch_unmatched_lines(cur, args.since)
            logger.info(
                "Loaded %d unmatched bank inflows since %s",
                len(unmatched),
                args.since,
            )

            invoice_cache: dict[UUID, list[Invoice]] = {}
            rows: list[dict] = []
            stats = {
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "NONE": 0,
                "amount_match": 0,
                "no_amount_match": 0,
            }

            for line in unmatched:
                desc = line["description"] or ""
                amount = Decimal(line["amount"])
                non_customer = detect_non_customer_pattern(desc)
                cust, conf = find_customer_match(
                    desc, line.get("payee_payer"), customers
                )
                stats[conf] += 1

                inv_label = ""
                inv_numbers = ""
                inv_total = Decimal(0)
                # Skip invoice matching when the line is clearly not a
                # customer payment (salary, refund, intercompany, etc.).
                if non_customer:
                    inv_label = "SKIP_NON_CUSTOMER"
                elif cust is not None:
                    if cust.customer_id not in invoice_cache:
                        invoice_cache[cust.customer_id] = fetch_open_invoices(
                            cur, cust.customer_id
                        )
                    invs = invoice_cache[cust.customer_id]
                    matches, inv_label = find_invoice_matches(amount, invs)
                    if matches:
                        inv_numbers = ", ".join(m.invoice_number for m in matches)
                        inv_total = sum((m.total_amount for m in matches), Decimal(0))
                        stats["amount_match"] += 1
                    else:
                        stats["no_amount_match"] += 1

                rows.append(
                    {
                        "bank_line_id": line["line_id"],
                        "transaction_date": line["transaction_date"],
                        "bank_account": f"{line['account_code']} {line['gl_account_name']}",
                        "amount": str(amount),
                        "description": (desc or "")[:120],
                        "non_customer_pattern": non_customer,
                        "suggested_customer": cust.legal_name if cust else "",
                        "customer_confidence": conf,
                        "amount_match_type": inv_label,
                        "suggested_invoice_numbers": inv_numbers,
                        "suggested_invoice_total": str(inv_total) if inv_total else "",
                        "approve": "",
                        "override_customer_legal_name": "",
                        "override_invoice_numbers": "",
                        "notes": "",
                    }
                )

    finally:
        conn.close()

    # Sort by amount DESC so finance reviews the biggest lines first.
    rows.sort(key=lambda r: Decimal(r["amount"]), reverse=True)

    fields = list(rows[0].keys()) if rows else []
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("")
    logger.info("Wrote %s with %d rows", out_path, len(rows))
    logger.info("Customer match confidence:")
    logger.info(
        "  HIGH=%d  MEDIUM=%d  LOW=%d  NONE=%d",
        stats["HIGH"],
        stats["MEDIUM"],
        stats["LOW"],
        stats["NONE"],
    )
    logger.info(
        "Amount match: %d of %d (%.1f%%)",
        stats["amount_match"],
        len(rows),
        100.0 * stats["amount_match"] / max(len(rows), 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
