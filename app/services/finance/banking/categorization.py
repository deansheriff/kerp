"""Transaction categorization service facade.

The method implementations live in ``categorization_parts``. This module keeps
the historical import path stable for callers and tests.
"""

from __future__ import annotations

from app.services.finance.banking.categorization_parts import (
    CategorizationCoreService,
    CategorizationEvaluationService,
    CategorizationPayeeService,
    CategorizationRuleService,
)
from app.services.finance.banking.categorization_parts.base import (
    BatchCategorizationResult,
    CategorizationResult,
    CategorizationSuggestion,
)


class TransactionCategorizationService(  # type: ignore[misc]
    CategorizationCoreService,
    CategorizationEvaluationService,
    CategorizationPayeeService,
    CategorizationRuleService,
):
    """Unified transaction categorization service facade."""


categorization_service = TransactionCategorizationService()


__all__ = [
    "BatchCategorizationResult",
    "CategorizationResult",
    "CategorizationSuggestion",
    "TransactionCategorizationService",
    "categorization_service",
]
