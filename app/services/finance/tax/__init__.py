"""
Tax Services.

Keep package import-light: many modules import submodules such as
`app.services.finance.tax.tax_calculation`, and eager imports here can cause
large dependency graphs (GL/AP/etc) to load during test collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from app.services.finance.tax.deferred_tax import (  # noqa: F401
        DeferredTaxBasisInput,
        DeferredTaxCalculationResult,
        DeferredTaxMovementResult,
        DeferredTaxService,
        DeferredTaxSummary,
        deferred_tax_service,
    )
    from app.services.finance.tax.fiscal_position_service import (  # noqa: F401
        FiscalPositionService,
    )
    from app.services.finance.tax.tax_calculation import (  # noqa: F401
        InvoiceLineTaxInput,
        InvoiceTaxResult,
        LineCalculationResult,
        LineTaxInput,
        LineTaxResult,
        TaxCalculationService,
        tax_calculation_service,
    )
    from app.services.finance.tax.tax_master import (  # noqa: F401
        TaxCalculationResult,
        TaxCodeInput,
        TaxCodeService,
        TaxJurisdictionInput,
        TaxJurisdictionService,
        tax_code_service,
        tax_jurisdiction_service,
    )
    from app.services.finance.tax.tax_period import (  # noqa: F401
        TaxPeriodInput,
        TaxPeriodService,
        tax_period_service,
    )
    from app.services.finance.tax.tax_posting_adapter import (  # noqa: F401
        TAXPostingAdapter,
        TAXPostingResult,
        tax_posting_adapter,
    )
    from app.services.finance.tax.tax_reconciliation import (  # noqa: F401
        ReconciliationLine,
        TaxReconciliationInput,
        TaxReconciliationService,
        tax_reconciliation_service,
    )
    from app.services.finance.tax.tax_return import (  # noqa: F401
        TaxReturnInput,
        TaxReturnService,
        TaxReturnUpdateInput,
        tax_return_service,
    )
    from app.services.finance.tax.tax_transaction import (  # noqa: F401
        TaxByCodeSummary,
        TaxReturnSummary,
        TaxTransactionCreateInput,
        TaxTransactionInput,
        TaxTransactionService,
        tax_transaction_service,
    )


__all__ = [
    # Tax Code
    "TaxCodeService",
    "TaxCodeInput",
    "TaxCalculationResult",
    "tax_code_service",
    # Tax Jurisdiction
    "TaxJurisdictionService",
    "TaxJurisdictionInput",
    "tax_jurisdiction_service",
    # Tax Transaction
    "TaxTransactionService",
    "TaxTransactionInput",
    "TaxTransactionCreateInput",
    "TaxReturnSummary",
    "TaxByCodeSummary",
    "tax_transaction_service",
    # Deferred Tax
    "DeferredTaxService",
    "DeferredTaxBasisInput",
    "DeferredTaxCalculationResult",
    "DeferredTaxMovementResult",
    "DeferredTaxSummary",
    "deferred_tax_service",
    # Tax Reconciliation
    "TaxReconciliationService",
    "TaxReconciliationInput",
    "ReconciliationLine",
    "tax_reconciliation_service",
    # Posting
    "TAXPostingAdapter",
    "TAXPostingResult",
    "tax_posting_adapter",
    # Tax Period
    "TaxPeriodService",
    "tax_period_service",
    "TaxPeriodInput",
    # Tax Return
    "TaxReturnService",
    "tax_return_service",
    "TaxReturnInput",
    "TaxReturnUpdateInput",
    # Tax Calculation
    "TaxCalculationService",
    "LineTaxInput",
    "LineTaxResult",
    "LineCalculationResult",
    "InvoiceLineTaxInput",
    "InvoiceTaxResult",
    "tax_calculation_service",
    # Fiscal Position
    "FiscalPositionService",
]


_NAME_TO_MODULE = {
    # deferred_tax
    "DeferredTaxBasisInput": "deferred_tax",
    "DeferredTaxCalculationResult": "deferred_tax",
    "DeferredTaxMovementResult": "deferred_tax",
    "DeferredTaxService": "deferred_tax",
    "DeferredTaxSummary": "deferred_tax",
    "deferred_tax_service": "deferred_tax",
    # fiscal_position_service
    "FiscalPositionService": "fiscal_position_service",
    # tax_calculation
    "InvoiceLineTaxInput": "tax_calculation",
    "InvoiceTaxResult": "tax_calculation",
    "LineCalculationResult": "tax_calculation",
    "LineTaxInput": "tax_calculation",
    "LineTaxResult": "tax_calculation",
    "TaxCalculationService": "tax_calculation",
    "tax_calculation_service": "tax_calculation",
    # tax_master
    "TaxCalculationResult": "tax_master",
    "TaxCodeInput": "tax_master",
    "TaxCodeService": "tax_master",
    "TaxJurisdictionInput": "tax_master",
    "TaxJurisdictionService": "tax_master",
    "tax_code_service": "tax_master",
    "tax_jurisdiction_service": "tax_master",
    # tax_period
    "TaxPeriodInput": "tax_period",
    "TaxPeriodService": "tax_period",
    "tax_period_service": "tax_period",
    # tax_posting_adapter
    "TAXPostingAdapter": "tax_posting_adapter",
    "TAXPostingResult": "tax_posting_adapter",
    "tax_posting_adapter": "tax_posting_adapter",
    # tax_reconciliation
    "ReconciliationLine": "tax_reconciliation",
    "TaxReconciliationInput": "tax_reconciliation",
    "TaxReconciliationService": "tax_reconciliation",
    "tax_reconciliation_service": "tax_reconciliation",
    # tax_return
    "TaxReturnInput": "tax_return",
    "TaxReturnService": "tax_return",
    "TaxReturnUpdateInput": "tax_return",
    "tax_return_service": "tax_return",
    # tax_transaction
    "TaxByCodeSummary": "tax_transaction",
    "TaxReturnSummary": "tax_transaction",
    "TaxTransactionCreateInput": "tax_transaction",
    "TaxTransactionInput": "tax_transaction",
    "TaxTransactionService": "tax_transaction",
    "tax_transaction_service": "tax_transaction",
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    module_name = _NAME_TO_MODULE.get(name)
    if not module_name:
        raise AttributeError(name)
    module = __import__(f"{__name__}.{module_name}", fromlist=[name])
    return getattr(module, name)
