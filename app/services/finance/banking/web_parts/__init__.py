"""Modular banking web service components."""

from app.services.finance.banking.web_parts.accounts import BankingAccountWebService
from app.services.finance.banking.web_parts.dashboard import BankingDashboardWebService
from app.services.finance.banking.web_parts.payees import BankingPayeeWebService
from app.services.finance.banking.web_parts.reconciliations import (
    BankingReconciliationWebService,
)
from app.services.finance.banking.web_parts.rules import BankingRuleWebService
from app.services.finance.banking.web_parts.statements import BankingStatementWebService

__all__ = [
    "BankingAccountWebService",
    "BankingDashboardWebService",
    "BankingPayeeWebService",
    "BankingReconciliationWebService",
    "BankingRuleWebService",
    "BankingStatementWebService",
]
