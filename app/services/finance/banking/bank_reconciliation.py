"""Bank reconciliation service facade.

The method implementations live in ``reconciliation_parts``. This module keeps
the historical import path stable for callers and tests.
"""

from __future__ import annotations

from app.services.finance.banking.reconciliation_parts import (
    ReconciliationCoreService,
    ReconciliationMatchingService,
    ReconciliationWorkflowService,
)
from app.services.finance.banking.reconciliation_parts.base import (
    AMOUNT_MISMATCH_ABSOLUTE_TOLERANCE,
    AMOUNT_MISMATCH_RELATIVE_THRESHOLD,
    SOURCE_URL_MAP,
    AutoMatchResult,
    MatchSuggestion,
    ReconciliationInput,
    ReconciliationMatchInput,
    _build_source_url,
    _check_rule_payee_link,
)


class BankReconciliationService(  # type: ignore[misc]
    ReconciliationCoreService,
    ReconciliationMatchingService,
    ReconciliationWorkflowService,
):
    """Unified bank reconciliation service facade."""


bank_reconciliation_service = BankReconciliationService()


__all__ = [
    "AutoMatchResult",
    "BankReconciliationService",
    "MatchSuggestion",
    "ReconciliationInput",
    "ReconciliationMatchInput",
    "AMOUNT_MISMATCH_ABSOLUTE_TOLERANCE",
    "AMOUNT_MISMATCH_RELATIVE_THRESHOLD",
    "SOURCE_URL_MAP",
    "_build_source_url",
    "_check_rule_payee_link",
    "bank_reconciliation_service",
]
