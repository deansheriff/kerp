"""Modular AP API routers."""

from app.api.finance.ap_routes.base import get_db, router
from app.api.finance.ap_routes import (
    aging,
    goods_receipts,
    invoices,
    payment_batches,
    payments,
    purchase_orders,
    suppliers,
)

__all__ = [
    "aging",
    "get_db",
    "goods_receipts",
    "invoices",
    "payment_batches",
    "payments",
    "purchase_orders",
    "router",
    "suppliers",
]
