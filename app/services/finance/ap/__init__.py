"""
AP (Accounts Payable) Services.

This package is on the import path for many submodules. Keep `__init__`
import-light and lazily load exports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from app.services.finance.ap.ap_aging import ap_aging_service  # noqa: F401
    from app.services.finance.ap.ap_posting_adapter import (  # noqa: F401
        APPostingAdapter,
        APPostingResult,
    )
    from app.services.finance.ap.goods_receipt import goods_receipt_service  # noqa: F401
    from app.services.finance.ap.payment_batch import payment_batch_service  # noqa: F401
    from app.services.finance.ap.purchase_order import (  # noqa: F401
        POLineInput,
        PurchaseOrderInput,
        PurchaseOrderService,
        purchase_order_service,
    )
    from app.services.finance.ap.supplier import (  # noqa: F401
        SupplierInput,
        SupplierService,
        supplier_service,
    )
    from app.services.finance.ap.supplier_invoice import (  # noqa: F401
        InvoiceLineInput,
        SupplierInvoiceInput,
        SupplierInvoiceService,
        supplier_invoice_service,
    )
    from app.services.finance.ap.supplier_payment import (  # noqa: F401
        PaymentAllocationInput,
        SupplierPaymentInput,
        SupplierPaymentService,
        supplier_payment_service,
    )


__all__ = [
    # Supplier
    "SupplierService",
    "SupplierInput",
    "supplier_service",
    # Supplier Invoice
    "SupplierInvoiceService",
    "SupplierInvoiceInput",
    "InvoiceLineInput",
    "supplier_invoice_service",
    # Supplier Payment
    "SupplierPaymentService",
    "SupplierPaymentInput",
    "PaymentAllocationInput",
    "supplier_payment_service",
    # AP Aging
    "ap_aging_service",
    # Posting Adapter (types only; instance re-exports intentionally omitted)
    "APPostingAdapter",
    "APPostingResult",
    # Purchase Order
    "PurchaseOrderService",
    "PurchaseOrderInput",
    "POLineInput",
    "purchase_order_service",
    # Goods Receipt
    "goods_receipt_service",
    # Payment Batch
    "payment_batch_service",
]


_NAME_TO_MODULE = {
    # supplier
    "SupplierService": "supplier",
    "SupplierInput": "supplier",
    "supplier_service": "supplier",
    # supplier_invoice
    "SupplierInvoiceService": "supplier_invoice",
    "SupplierInvoiceInput": "supplier_invoice",
    "InvoiceLineInput": "supplier_invoice",
    "supplier_invoice_service": "supplier_invoice",
    # supplier_payment
    "SupplierPaymentService": "supplier_payment",
    "SupplierPaymentInput": "supplier_payment",
    "PaymentAllocationInput": "supplier_payment",
    "supplier_payment_service": "supplier_payment",
    # ap_aging
    "ap_aging_service": "ap_aging",
    # ap_posting_adapter
    "APPostingAdapter": "ap_posting_adapter",
    "APPostingResult": "ap_posting_adapter",
    # purchase_order
    "PurchaseOrderService": "purchase_order",
    "PurchaseOrderInput": "purchase_order",
    "POLineInput": "purchase_order",
    "purchase_order_service": "purchase_order",
    # goods_receipt
    "goods_receipt_service": "goods_receipt",
    # payment_batch
    "payment_batch_service": "payment_batch",
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    module_name = _NAME_TO_MODULE.get(name)
    if not module_name:
        raise AttributeError(name)
    module = __import__(f"{__name__}.{module_name}", fromlist=[name])
    return getattr(module, name)
