# ruff: noqa: F401
"""
Transaction Categorization Service.

Provides auto-categorization of bank transactions using payee matching
and configurable rules.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.finance.banking.bank_account import BankAccount, BankAccountStatus
from app.models.finance.banking.bank_statement import (
    BankStatement,
    BankStatementLine,
    StatementLineType,
)
from app.models.finance.banking.payee import Payee, PayeeType
from app.models.finance.banking.transaction_rule import (
    RuleAction,
    RuleType,
    TransactionRule,
)
from app.services.common import coerce_uuid

logger = logging.getLogger(__name__)


@dataclass
class CategorizationSuggestion:
    """A suggested categorization for a transaction."""

    account_id: UUID | None = None
    account_name: str | None = None
    tax_code_id: UUID | None = None
    payee_id: UUID | None = None
    payee_name: str | None = None
    rule_id: UUID | None = None
    rule_name: str | None = None
    confidence: int = 0  # 0-100
    match_reason: str = ""
    action: RuleAction = RuleAction.CATEGORIZE
    split_config: dict | None = None


@dataclass
class CategorizationResult:
    """Result of categorizing a single transaction."""

    line_id: UUID
    suggestions: list[CategorizationSuggestion] = field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: UUID | None = None

    @property
    def best_suggestion(self) -> CategorizationSuggestion | None:
        """Get the highest confidence suggestion."""
        if not self.suggestions:
            return None
        return max(self.suggestions, key=lambda s: s.confidence)

    @property
    def has_high_confidence_match(self) -> bool:
        """Check if there's a high confidence match (>80%)."""
        return any(s.confidence >= 80 for s in self.suggestions)


@dataclass
class BatchCategorizationResult:
    """Result of categorizing multiple transactions."""

    total_lines: int = 0
    categorized_count: int = 0
    high_confidence_count: int = 0
    low_confidence_count: int = 0
    no_match_count: int = 0
    duplicate_count: int = 0
    results: list[CategorizationResult] = field(default_factory=list)


__all__ = [name for name in globals() if not name.startswith("__")]
