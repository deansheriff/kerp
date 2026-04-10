"""AR API router compatibility module."""

from app.api.finance.ar_routes import get_db, router
from app.api.finance.ar_routes.contracts import (
    ContractCreate,
    ContractRead,
    PerformanceObligationCreate,
    ProgressUpdateCreate,
    RevenueEventRead,
)

__all__ = [
    "ContractCreate",
    "ContractRead",
    "PerformanceObligationCreate",
    "ProgressUpdateCreate",
    "RevenueEventRead",
    "get_db",
    "router",
]
