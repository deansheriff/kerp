"""Post stranded APPROVED bank-fee journals from the March 2026 Mono import.

The Mono import migration created 429 ``BANKING`` / ``BANK_FEE`` journals
in FY2025 with status ``APPROVED`` but never advanced them to ``POSTED``.
Until they are posted:

  * GL account ``6080 Finance Cost`` is understated by their total
    (~NGN 7,765 across Jan–Sep 2025).
  * Bank reconciliations for ``Paystack OPEX`` and ``Zenith USD`` will not
    tie to the bank statements (the fees were deducted by the bank).
  * The ``gl.posted_ledger_line`` table is missing the corresponding
    rows, so trial balance and bank-balance queries skip them silently.

This script drives ``LedgerPostingService.post_journal_entry`` — the same
single-writer used by normal AP/AR flows — so every artifact a real post
creates (``posting_batch`` row, ``posted_ledger_line`` rows, balance
invalidations, outbox event, hook event) is created identically.

Idempotency is per journal. The key is
``backfill-stranded-bank-fees-{journal_number}``. The posting service
detects an existing POSTED batch with the same key and returns success
without re-posting, so re-runs are safe.

Per-journal commit. A failure on one journal does not roll back the
others — re-run with ``--execute`` to retry only the ones that failed
(idempotency makes re-runs cheap).

Usage::

    # Dry run (default) — list what would be posted, no DB writes
    python scripts/post_stranded_bank_fees.py

    # Execute — post the journals (per-journal commit)
    python scripts/post_stranded_bank_fees.py --execute

    # Smoke-test against a single journal first
    python scripts/post_stranded_bank_fees.py --execute --limit 1
"""

from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.finance.gl.fiscal_period import FiscalPeriod  # noqa: E402
from app.models.finance.gl.fiscal_year import FiscalYear  # noqa: E402
from app.models.finance.gl.journal_entry import (  # noqa: E402
    JournalEntry,
    JournalStatus,
)
from app.services.finance.gl.ledger_posting import (  # noqa: E402
    LedgerPostingService,
    PostingRequest,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("post_stranded_bank_fees")

# Quiet the framework loggers so script output is readable.
for noisy in ("sqlalchemy.engine", "app.services.finance.gl.ledger_posting"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


SOURCE_MODULE = "BANKING"
SOURCE_DOC_TYPE = "BANK_FEE"
TARGET_YEAR_CODE = "FY2025"
IDEMPOTENCY_PREFIX = "backfill-stranded-bank-fees"


def fetch_stranded_journals(
    db: Session,
    limit: int | None = None,
) -> list[JournalEntry]:
    stmt = (
        select(JournalEntry)
        .join(
            FiscalPeriod,
            FiscalPeriod.fiscal_period_id == JournalEntry.fiscal_period_id,
        )
        .join(
            FiscalYear,
            FiscalYear.fiscal_year_id == FiscalPeriod.fiscal_year_id,
        )
        .where(
            FiscalYear.year_code == TARGET_YEAR_CODE,
            JournalEntry.status == JournalStatus.APPROVED,
            JournalEntry.source_module == SOURCE_MODULE,
            JournalEntry.source_document_type == SOURCE_DOC_TYPE,
        )
        .order_by(JournalEntry.posting_date, JournalEntry.journal_number)
    )
    if limit:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def post_one(db: Session, journal: JournalEntry) -> tuple[bool, str]:
    """Post a single journal via the standard service. Returns (success, message)."""
    request = PostingRequest(
        organization_id=journal.organization_id,
        journal_entry_id=journal.journal_entry_id,
        posting_date=journal.posting_date,
        idempotency_key=f"{IDEMPOTENCY_PREFIX}-{journal.journal_number}",
        source_module=SOURCE_MODULE,
        # Leaving entries=[] tells the service to load lines from journal_entry_line.
        posted_by_user_id=journal.approved_by_user_id or journal.created_by_user_id,
        correlation_id=f"{IDEMPOTENCY_PREFIX}-{journal.journal_number}",
    )
    try:
        result = LedgerPostingService.post_journal_entry(db, request)
        return bool(result.success), result.message or "ok"
    except Exception as e:  # noqa: BLE001 — per-journal failure handled below
        return False, f"{type(e).__name__}: {e}"


def dry_run_report(journals: list[JournalEntry]) -> None:
    total_debit = sum(j.total_debit_functional for j in journals)
    logger.info(
        "[DRY RUN] would post %d journals (total functional debit %s)",
        len(journals),
        total_debit,
    )
    sample = journals[:10]
    for j in sample:
        desc = (j.description or "")[:60]
        logger.info(
            "  %s | %s | DR %s | %s",
            j.journal_number,
            j.posting_date,
            j.total_debit_functional,
            desc,
        )
    if len(journals) > len(sample):
        logger.info(
            "  ... and %d more (use --execute to post all)", len(journals) - len(sample)
        )


def execute(journals: list[JournalEntry]) -> int:
    """Post each journal in its own transaction. Returns process exit code."""
    succeeded = 0
    skipped = 0  # Already posted (idempotent replay)
    failures: list[tuple[str, str]] = []

    total = len(journals)
    for i, journal in enumerate(journals, start=1):
        # Each journal in its own session/transaction so failures don't taint others.
        with SessionLocal() as db:
            ok, msg = post_one(db, journal)
            if ok:
                if "Already posted" in msg:
                    skipped += 1
                    db.rollback()
                else:
                    db.commit()
                    succeeded += 1
            else:
                db.rollback()
                failures.append((journal.journal_number, msg))
                logger.error("FAIL %s: %s", journal.journal_number, msg)

        if i % 50 == 0 or i == total:
            logger.info(
                "Progress: %d/%d (posted=%d, idempotent_skip=%d, failed=%d)",
                i,
                total,
                succeeded,
                skipped,
                len(failures),
            )

    logger.info(
        "Done. posted=%d, idempotent_skip=%d, failed=%d, total=%d",
        succeeded,
        skipped,
        len(failures),
        total,
    )
    if failures:
        logger.error("=== Failures ===")
        for jn, msg in failures[:20]:
            logger.error("  %s: %s", jn, msg)
        if len(failures) > 20:
            logger.error("  ... and %d more", len(failures) - 20)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Post stranded APPROVED FY2025 BANK_FEE journals via "
            "LedgerPostingService. Dry-run by default."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually post the journals. Without this flag, the script is a dry run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to N journals (useful for smoke-testing).",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        journals = fetch_stranded_journals(db, limit=args.limit)

    logger.info(
        "Found %d stranded APPROVED %s/%s journals in %s",
        len(journals),
        SOURCE_MODULE,
        SOURCE_DOC_TYPE,
        TARGET_YEAR_CODE,
    )

    if not journals:
        logger.info("Nothing to do.")
        return 0

    if not args.execute:
        dry_run_report(journals)
        logger.info("Re-run with --execute to post.")
        return 0

    return execute(journals)


if __name__ == "__main__":
    sys.exit(main())
