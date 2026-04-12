"""Rule-driven reconciliation engine facade.

The method implementations live in ``reconciliation_engine_parts``. This module
keeps the historical import path stable.
"""

from __future__ import annotations

from app.services.finance.banking.reconciliation_engine_parts import (
    ReconciliationEngineCore,
    ReconciliationEngineHandlers,
    ReconciliationEngineHelpers,
)
from app.services.finance.banking.reconciliation_engine_parts.base import (
    EngineContext,
    EngineMatch,
    EngineResult,
)


class ReconciliationEngine(  # type: ignore[misc]
    ReconciliationEngineCore,
    ReconciliationEngineHandlers,
    ReconciliationEngineHelpers,
):
    """Unified reconciliation engine facade."""


__all__ = [
    "EngineContext",
    "EngineMatch",
    "EngineResult",
    "ReconciliationEngine",
]
