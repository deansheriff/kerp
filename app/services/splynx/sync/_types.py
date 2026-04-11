from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, TypedDict


class PaystackReconcileResult(TypedDict):
    matched_by_reference: int
    matched_by_date_amount: int
    matched_by_customer: int
    matched_by_score_gap: int
    matched_opening_balance: int
    ambiguous_matches: int
    unmatched_payments: int
    unmatched_statements: int
    total_matched_amount: Decimal
    review_queue: list[dict[str, Any]]
    errors: list[str]


class BankReconcileResult(TypedDict):
    bank_name: str
    matched_by_date_amount: int
    matched_by_customer: int
    ambiguous_matches: int
    unmatched_payments: int
    unmatched_statements: int
    total_matched_amount: Decimal
    errors: list[str]


class BulkReconcileResult(TypedDict):
    bank_name: str
    bulk_matches: int
    payments_matched: int
    total_matched_amount: Decimal
    errors: list[str]


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    entity_type: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "entity_type": self.entity_type,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "message": self.message,
        }


@dataclass
class FullSyncResult:
    """Result of a full sync operation (all entity types)."""

    customers: SyncResult
    invoices: SyncResult
    payments: SyncResult
    credit_notes: SyncResult
    ledger_resolution: dict[str, Any] = field(default_factory=dict)
    total_errors: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "customers": self.customers.to_dict(),
            "invoices": self.invoices.to_dict(),
            "payments": self.payments.to_dict(),
            "credit_notes": self.credit_notes.to_dict(),
            "ledger_resolution": self.ledger_resolution,
            "total_errors": self.total_errors,
            "duration_seconds": self.duration_seconds,
        }
