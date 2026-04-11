"""
Splynx Sync Service — package.

Re-exports public API so that existing imports like::

    from app.services.splynx.sync import SplynxSyncService

continue to work unchanged.
"""

from __future__ import annotations

from app.models.finance.ar.payment_allocation import (
    PaymentAllocation,
)

from ._constants import (
    SPLYNX_SYNC_MIN_DATE,
    SYSTEM_USER_ID,
    _PRE_CUTOFF_SENTINEL,
)
from ._service import SplynxSyncService
from ._types import (
    BankReconcileResult,
    BulkReconcileResult,
    FullSyncResult,
    PaystackReconcileResult,
    SyncResult,
)

__all__ = [
    "BankReconcileResult",
    "BulkReconcileResult",
    "FullSyncResult",
    "PaymentAllocation",
    "PaystackReconcileResult",
    "SPLYNX_SYNC_MIN_DATE",
    "SYSTEM_USER_ID",
    "SplynxSyncService",
    "SyncResult",
    "_PRE_CUTOFF_SENTINEL",
]
