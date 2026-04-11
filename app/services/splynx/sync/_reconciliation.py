from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

from sqlalchemy import text

from ._reconciliation_bank import BankReconciliationMixin
from ._types import (
    PaystackReconcileResult,
)

logger = logging.getLogger(__name__)


def _to_date(value: Any) -> date | None:
    """Coerce a datetime/date/None to date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


class ReconciliationMixin(BankReconciliationMixin):
    """Paystack reconciliation + bank reconciliation (via BankReconciliationMixin)."""

    # Provided by other mixins at runtime
    db: Any
    organization_id: UUID

    def reconcile_paystack_payments(
        self,
        dry_run: bool = False,
    ) -> PaystackReconcileResult:
        """Reconcile Splynx Paystack payments with bank statements.

        Four-tier matching:
        1. Exact match by Paystack reference
        2. Unique match by amount + date window
        3. Customer-based match by amount + date window
        4. Score-gap disambiguation for remaining ambiguous
        """
        logger.info(
            "Starting Paystack payment reconciliation (dry_run=%s)",
            dry_run,
        )

        result: PaystackReconcileResult = {
            "matched_by_reference": 0,
            "matched_by_date_amount": 0,
            "matched_by_customer": 0,
            "matched_by_score_gap": 0,
            "matched_opening_balance": 0,
            "ambiguous_matches": 0,
            "unmatched_payments": 0,
            "unmatched_statements": 0,
            "total_matched_amount": Decimal("0"),
            "review_queue": [],
            "errors": [],
        }

        paystack_accounts = self.db.execute(
            text("""
                SELECT bank_account_id
                FROM banking.bank_accounts
                WHERE organization_id = :org_id
                  AND (LOWER(account_name) LIKE '%paystack%'
                       OR LOWER(bank_name) LIKE '%paystack%')
            """),
            {"org_id": self.organization_id},
        ).fetchall()

        if not paystack_accounts:
            result["errors"].append("No Paystack bank accounts found")
            return result

        paystack_account_ids = [row.bank_account_id for row in paystack_accounts]
        logger.info(
            "Found %d Paystack bank accounts",
            len(paystack_account_ids),
        )

        # Step 1: Reference matching
        payments_with_refs = self.db.execute(
            text("""
                SELECT
                    cp.payment_id,
                    cp.payment_date,
                    cp.amount,
                    cp.reference,
                    cp.description
                FROM ar.customer_payment cp
                WHERE cp.organization_id = :org_id
                  AND cp.correlation_id LIKE 'splynx-pmt-%%'
                  AND cp.bank_account_id = ANY(:account_ids)
                  AND (
                    cp.description ~* '[0-9a-f]{12,14}'
                    OR cp.reference ~* '[0-9a-f]{12,14}'
                  )
            """),
            {
                "org_id": self.organization_id,
                "account_ids": paystack_account_ids,
            },
        ).fetchall()

        logger.info(
            "Found %d payments with Paystack references",
            len(payments_with_refs),
        )

        statement_refs = self.db.execute(
            text("""
                SELECT
                    bsl.line_id,
                    bsl.reference,
                    bsl.description,
                    bsl.amount,
                    bsl.transaction_date,
                    bsl.is_matched
                FROM banking.bank_statement_lines bsl
                JOIN banking.bank_statements bs
                  ON bsl.statement_id = bs.statement_id
                WHERE bs.organization_id = :org_id
                  AND bs.bank_account_id = ANY(:account_ids)
                  AND bsl.transaction_type = 'credit'
                  AND bsl.is_matched = false
            """),
            {
                "org_id": self.organization_id,
                "account_ids": paystack_account_ids,
            },
        ).fetchall()

        matched_payment_ids: set[UUID] = set()
        matched_line_ids: set[UUID] = set()

        # Opening balance carry-forwards
        self._match_opening_balance_lines(
            statement_refs, matched_line_ids, result, dry_run
        )

        token_pattern = re.compile(r"\b[0-9a-f]{12,14}\b", re.IGNORECASE)

        def _extract_paystack_tokens(*values: str | None) -> set[str]:
            tokens: set[str] = set()
            for value in values:
                if not value:
                    continue
                tokens.update(m.group(0).lower() for m in token_pattern.finditer(value))
            return tokens

        token_to_lines: dict[str, list[Any]] = defaultdict(list)
        for row in statement_refs:
            if row.line_id in matched_line_ids:
                continue
            for token in _extract_paystack_tokens(
                getattr(row, "reference", None),
                getattr(row, "description", None),
            ):
                token_to_lines[token].append(row)

        logger.info("Found %d unmatched statement lines", len(statement_refs))

        # Match by reference token
        for payment in payments_with_refs:
            payment_tokens = _extract_paystack_tokens(
                getattr(payment, "reference", None),
                getattr(payment, "description", None),
            )
            if not payment_tokens:
                continue

            candidate_lines: list[Any] = []
            for token in payment_tokens:
                candidate_lines.extend(token_to_lines.get(token, []))

            deduped_candidates = {
                line.line_id: line
                for line in candidate_lines
                if line.line_id not in matched_line_ids
            }
            if not deduped_candidates:
                continue

            amount_cents = int(payment.amount * 100)
            amount_matched = [
                line
                for line in deduped_candidates.values()
                if int(line.amount * 100) == amount_cents
            ]
            chosen = amount_matched or list(deduped_candidates.values())
            if len(chosen) != 1:
                continue

            line = chosen[0]
            matched_payment_ids.add(payment.payment_id)
            matched_line_ids.add(line.line_id)
            result["matched_by_reference"] += 1
            result["total_matched_amount"] += payment.amount

            if not dry_run:
                self._mark_line_matched(
                    line.line_id,
                    f" [Matched to Splynx payment "
                    f"{payment.payment_id} by paystack token]",
                )

        logger.info("Matched %d payments by reference", result["matched_by_reference"])

        # Step 2: Amount + date window matching
        unmatched_payments = self.db.execute(
            text("""
                SELECT
                    cp.payment_id, cp.customer_id, cp.payment_date,
                    cp.amount, cp.reference, cp.description
                FROM ar.customer_payment cp
                WHERE cp.organization_id = :org_id
                  AND cp.correlation_id LIKE 'splynx-pmt-%%'
                  AND cp.bank_account_id = ANY(:account_ids)
                  AND cp.payment_id != ALL(:matched_ids)
            """),
            {
                "org_id": self.organization_id,
                "account_ids": paystack_account_ids,
                "matched_ids": list(matched_payment_ids)
                or [UUID("00000000-0000-0000-0000-000000000000")],
            },
        ).fetchall()

        unmatched_lines = self.db.execute(
            text("""
                SELECT
                    bsl.line_id, bsl.transaction_date, bsl.amount,
                    bsl.reference, bsl.description
                FROM banking.bank_statement_lines bsl
                JOIN banking.bank_statements bs
                  ON bsl.statement_id = bs.statement_id
                WHERE bs.organization_id = :org_id
                  AND bs.bank_account_id = ANY(:account_ids)
                  AND bsl.transaction_type = 'credit'
                  AND bsl.is_matched = false
                  AND bsl.line_id != ALL(:matched_ids)
            """),
            {
                "org_id": self.organization_id,
                "account_ids": paystack_account_ids,
                "matched_ids": list(matched_line_ids)
                or [UUID("00000000-0000-0000-0000-000000000000")],
            },
        ).fetchall()

        amount_index: dict[int, list[UUID]] = {}
        for line in unmatched_lines:
            amount_cents = int(line.amount * 100)
            if amount_cents not in amount_index:
                amount_index[amount_cents] = []
            amount_index[amount_cents].append(line.line_id)
        line_meta_by_id = {line.line_id: line for line in unmatched_lines}

        DATE_WINDOW_DAYS_BEFORE = 3
        DATE_WINDOW_DAYS_AFTER = 7

        def _candidate_lines_for_amount_date(
            payment_date: Any, amt_cents: int
        ) -> list[UUID]:
            payment_day = _to_date(payment_date)
            if payment_day is None:
                return []
            ranked: list[tuple[int, int, int, UUID]] = []
            for lid in amount_index.get(amt_cents, []):
                if lid in matched_line_ids:
                    continue
                ln = line_meta_by_id.get(lid)
                if ln is None:
                    continue
                line_day = _to_date(getattr(ln, "transaction_date", None))
                if line_day is None:
                    continue
                day_delta = (line_day - payment_day).days
                if (
                    day_delta < -DATE_WINDOW_DAYS_BEFORE
                    or day_delta > DATE_WINDOW_DAYS_AFTER
                ):
                    continue
                ranked.append(
                    (0 if day_delta == 0 else 1, abs(day_delta), day_delta, lid)
                )
            ranked.sort()
            return [lid for _, _, _, lid in ranked]

        # Tier 2: unique amount+date-window
        ambiguous_payments: list[Any] = []
        for payment in unmatched_payments:
            if payment.payment_id in matched_payment_ids:
                continue
            amount_cents = int(payment.amount * 100)
            available_lines = _candidate_lines_for_amount_date(
                payment.payment_date, amount_cents
            )
            if len(available_lines) == 1:
                line_id = available_lines[0]
                matched_payment_ids.add(payment.payment_id)
                matched_line_ids.add(line_id)
                result["matched_by_date_amount"] += 1
                result["total_matched_amount"] += payment.amount
                if not dry_run:
                    ln = line_meta_by_id.get(line_id)
                    pday = _to_date(payment.payment_date)
                    lday = _to_date(getattr(ln, "transaction_date", None))
                    dd = (lday - pday).days if pday and lday else 0
                    self._mark_line_matched(
                        line_id,
                        f" [Matched to Splynx payment {payment.payment_id} "
                        f"by amount+date-window (delta_days={dd})]",
                    )
            elif len(available_lines) > 1:
                ambiguous_payments.append(payment)

        logger.info(
            "Tier 2 complete: %d matched by amount+date-window, %d ambiguous for tier 3",
            result["matched_by_date_amount"],
            len(ambiguous_payments),
        )

        # Tier 2b, 3, 4
        self._match_exact_date_amount_buckets(
            ambiguous_payments,
            unmatched_lines,
            matched_payment_ids,
            matched_line_ids,
            result,
            dry_run,
        )
        self._match_by_customer(
            ambiguous_payments,
            matched_payment_ids,
            matched_line_ids,
            _candidate_lines_for_amount_date,
            line_meta_by_id,
            result,
            dry_run,
        )
        self._match_by_score_gap(
            ambiguous_payments,
            matched_payment_ids,
            matched_line_ids,
            _candidate_lines_for_amount_date,
            line_meta_by_id,
            result,
            dry_run,
        )

        result["unmatched_payments"] = max(
            0,
            len(unmatched_payments)
            - (
                result["matched_by_date_amount"]
                + result["matched_by_customer"]
                + result["matched_by_score_gap"]
            ),
        )
        result["unmatched_statements"] = max(
            0, len(unmatched_lines) - len(matched_line_ids)
        )
        result["ambiguous_matches"] = len(result["review_queue"])

        if not dry_run:
            self.db.flush()

        logger.info(
            "Reconciliation complete: %d by ref, %d by date+amount, %d by customer, "
            "%d by score-gap, %d opening balance, %d ambiguous",
            result["matched_by_reference"],
            result["matched_by_date_amount"],
            result["matched_by_customer"],
            result["matched_by_score_gap"],
            result["matched_opening_balance"],
            result["ambiguous_matches"],
        )

        return result

    # -----------------------------------------------------------------
    # Paystack sub-steps
    # -----------------------------------------------------------------

    def _match_opening_balance_lines(
        self,
        statement_refs: list[Any],
        matched_line_ids: set[UUID],
        result: PaystackReconcileResult,
        dry_run: bool,
    ) -> None:
        """Mark opening balance carry-forward lines."""
        opening_balance_lines = [
            row
            for row in statement_refs
            if (getattr(row, "reference", "") or "").lower().startswith("ob-")
            or "opening balance" in ((getattr(row, "description", "") or "").lower())
        ]
        if opening_balance_lines:
            logger.info("Found %d opening-balance lines", len(opening_balance_lines))
        for line in opening_balance_lines:
            if line.line_id in matched_line_ids:
                continue
            matched_line_ids.add(line.line_id)
            result["matched_opening_balance"] += 1
            if not dry_run:
                self._mark_line_matched(
                    line.line_id,
                    " [Marked matched: opening balance / carry-forward settlement "
                    "(not a Splynx payment)]",
                )

    def _match_exact_date_amount_buckets(
        self,
        ambiguous_payments: list[Any],
        unmatched_lines: list[Any],
        matched_payment_ids: set[UUID],
        matched_line_ids: set[UUID],
        result: PaystackReconcileResult,
        dry_run: bool,
    ) -> None:
        """Resolve exact date+amount many-to-many buckets."""
        ambiguous_by_key: dict[tuple[object, int], list[Any]] = defaultdict(list)
        for payment in ambiguous_payments:
            if payment.payment_id in matched_payment_ids:
                continue
            key = (payment.payment_date, int(payment.amount * 100))
            ambiguous_by_key[key].append(payment)

        line_ids_by_key: dict[tuple[object, int], list[UUID]] = defaultdict(list)
        for line in unmatched_lines:
            if line.line_id in matched_line_ids:
                continue
            key = (line.transaction_date, int(line.amount * 100))
            line_ids_by_key[key].append(line.line_id)

        for key, payments in ambiguous_by_key.items():
            candidate_line_ids = [
                lid
                for lid in line_ids_by_key.get(key, [])
                if lid not in matched_line_ids
            ]
            if not payments or not candidate_line_ids:
                continue
            if len(payments) != len(candidate_line_ids):
                continue
            sorted_payments = sorted(payments, key=lambda p: str(p.payment_id))
            sorted_lines = sorted(candidate_line_ids, key=str)
            for payment, line_id in zip(sorted_payments, sorted_lines, strict=False):
                matched_payment_ids.add(payment.payment_id)
                matched_line_ids.add(line_id)
                result["matched_by_date_amount"] += 1
                result["total_matched_amount"] += payment.amount
                if not dry_run:
                    self._mark_line_matched(
                        line_id,
                        f" [Matched to Splynx payment {payment.payment_id} "
                        "by exact date+amount bucket]",
                    )

    def _match_by_customer(
        self,
        ambiguous_payments: list[Any],
        matched_payment_ids: set[UUID],
        matched_line_ids: set[UUID],
        candidate_fn: Any,
        line_meta_by_id: dict[UUID, Any],
        result: PaystackReconcileResult,
        dry_run: bool,
    ) -> None:
        """Tier 3: Customer-based matching for ambiguous payments."""
        customer_payment_groups: dict[tuple[UUID, object, int], list[Any]] = (
            defaultdict(list)
        )
        for payment in ambiguous_payments:
            if payment.payment_id in matched_payment_ids:
                continue
            amount_cents = int(payment.amount * 100)
            customer_key = (payment.customer_id, payment.payment_date, amount_cents)
            customer_payment_groups[customer_key].append(payment)

        for (_cid, pay_date, amount_cents), payments in customer_payment_groups.items():
            if len(payments) != 1:
                result["ambiguous_matches"] += len(payments)
                continue
            payment = payments[0]
            if payment.payment_id in matched_payment_ids:
                continue
            available_lines = candidate_fn(pay_date, amount_cents)
            if len(available_lines) == 1:
                line_id = available_lines[0]
                matched_payment_ids.add(payment.payment_id)
                matched_line_ids.add(line_id)
                result["matched_by_customer"] += 1
                result["total_matched_amount"] += payment.amount
                if not dry_run:
                    ln = line_meta_by_id.get(line_id)
                    pday = _to_date(payment.payment_date)
                    lday = _to_date(getattr(ln, "transaction_date", None))
                    dd = (lday - pday).days if pday and lday else 0
                    self._mark_line_matched(
                        line_id,
                        f" [Matched to Splynx payment {payment.payment_id} "
                        f"by customer+amount+date-window (delta_days={dd})]",
                    )
            else:
                result["ambiguous_matches"] += 1

    def _match_by_score_gap(
        self,
        ambiguous_payments: list[Any],
        matched_payment_ids: set[UUID],
        matched_line_ids: set[UUID],
        candidate_fn: Any,
        line_meta_by_id: dict[UUID, Any],
        result: PaystackReconcileResult,
        dry_run: bool,
    ) -> None:
        """Tier 4: Score-gap resolution for remaining ambiguous."""
        unresolved = [
            p for p in ambiguous_payments if p.payment_id not in matched_payment_ids
        ]

        def _normalize_text(value: str | None) -> str:
            if not value:
                return ""
            return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

        def _extract_tokens(value: str | None) -> set[str]:
            normalized = _normalize_text(value)
            if not normalized:
                return set()
            return {tok for tok in normalized.split() if len(tok) >= 4}

        proposals: list[dict[str, Any]] = []
        for payment in unresolved:
            amount_cents = int(payment.amount * 100)
            available_lines = candidate_fn(payment.payment_date, amount_cents)
            if not available_lines:
                continue
            payment_ref = _normalize_text(getattr(payment, "reference", None))
            payment_desc = _normalize_text(getattr(payment, "description", None))
            payment_tokens = _extract_tokens(payment_ref) | _extract_tokens(
                payment_desc
            )
            scored: list[tuple[float, UUID]] = []
            payment_day = _to_date(payment.payment_date)
            for line_id in available_lines:
                line = line_meta_by_id.get(line_id)
                if not line:
                    continue
                score = self._compute_match_score(
                    payment_ref,
                    payment_desc,
                    payment_tokens,
                    payment_day,
                    line,
                    _normalize_text,
                    _extract_tokens,
                )
                scored.append((min(score, 100.0), line_id))
            if not scored:
                continue
            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_line_id = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            proposals.append(
                {
                    "payment": payment,
                    "best_line_id": best_line_id,
                    "best_score": best_score,
                    "second_score": second_score,
                    "score_gap": best_score - second_score,
                    "candidates": scored[:5],
                }
            )

        proposals.sort(key=lambda p: (p["score_gap"], p["best_score"]), reverse=True)

        used_lines: set[UUID] = set()
        review_queue: list[dict[str, Any]] = []
        MIN_SCORE = 60.0
        MIN_GAP = 20.0
        for item in proposals:
            payment = item["payment"]
            best_lid: UUID = item["best_line_id"]
            if payment.payment_id in matched_payment_ids or best_lid in used_lines:
                continue
            line = line_meta_by_id.get(best_lid)
            if line is None:
                continue
            if item["best_score"] >= MIN_SCORE and item["score_gap"] >= MIN_GAP:
                matched_payment_ids.add(payment.payment_id)
                matched_line_ids.add(best_lid)
                used_lines.add(best_lid)
                result["matched_by_score_gap"] += 1
                result["total_matched_amount"] += payment.amount
                if not dry_run:
                    self._mark_line_matched(
                        best_lid,
                        f" [Matched to Splynx payment {payment.payment_id} by "
                        f"score-gap (score={item['best_score']:.1f}, "
                        f"gap={item['score_gap']:.1f})]",
                    )
            else:
                review_queue.append(
                    {
                        "payment_id": str(payment.payment_id),
                        "payment_date": str(payment.payment_date),
                        "amount": str(payment.amount),
                        "payment_reference": getattr(payment, "reference", None),
                        "payment_description": getattr(payment, "description", None),
                        "best_score": round(float(item["best_score"]), 1),
                        "score_gap": round(float(item["score_gap"]), 1),
                        "candidates": [
                            {
                                "line_id": str(lid),
                                "score": round(float(sc), 1),
                                "reference": getattr(
                                    line_meta_by_id.get(lid), "reference", None
                                ),
                                "description": getattr(
                                    line_meta_by_id.get(lid), "description", None
                                ),
                            }
                            for sc, lid in item["candidates"]
                        ],
                    }
                )

        result["review_queue"] = review_queue

    @staticmethod
    def _compute_match_score(
        payment_ref: str,
        payment_desc: str,
        payment_tokens: set[str],
        payment_day: date | None,
        line: Any,
        normalize_fn: Any,
        token_fn: Any,
    ) -> float:
        """Compute a match score for a payment-line pair."""
        line_ref = normalize_fn(getattr(line, "reference", None))
        line_desc = normalize_fn(getattr(line, "description", None))
        line_tokens = token_fn(line_ref) | token_fn(line_desc)
        line_day = _to_date(getattr(line, "transaction_date", None))
        day_delta = (
            (line_day - payment_day).days
            if payment_day is not None and line_day is not None
            else None
        )
        score = 20.0
        if day_delta is not None:
            if day_delta == 0:
                score += 20
            elif abs(day_delta) <= 1:
                score += 14
            elif abs(day_delta) <= 3:
                score += 8
            else:
                score += 3
        if payment_ref and line_ref and payment_ref == line_ref:
            score += 60
        elif payment_ref and (payment_ref in line_desc or payment_ref in line_ref):
            score += 25
        if line_ref and (line_ref in payment_desc or line_ref in payment_ref):
            score += 20
        common_tokens = payment_tokens & line_tokens
        if common_tokens:
            score += min(float(len(common_tokens) * 4), 10.0)
        return score
