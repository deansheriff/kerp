"""Banking web view service facade.

The resource-specific implementations live in ``web_parts``. This module keeps
the historical import path stable for web routes and tests.
"""

from __future__ import annotations

from app.services.finance.banking.web_parts import (
    BankingAccountWebService,
    BankingDashboardWebService,
    BankingPayeeWebService,
    BankingReconciliationWebService,
    BankingRuleWebService,
    BankingStatementWebService,
)
from app.services.finance.banking.web_parts.base import (
    _statement_line_view,
    bank_statement_service,
)


class BankingWebService(  # type: ignore[misc]
    BankingAccountWebService,
    BankingStatementWebService,
    BankingReconciliationWebService,
    BankingPayeeWebService,
    BankingRuleWebService,
    BankingDashboardWebService,
):
    """Unified banking web service facade."""


banking_web_service = BankingWebService()


__all__ = [
    "BankingWebService",
    "_statement_line_view",
    "bank_statement_service",
    "banking_web_service",
]
