from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.splynx.client import SplynxConfig

from ._allocations import AllocationMixin
from ._bank_mapping import BankMappingMixin
from ._base import BaseSyncMixin
from ._credit_notes import CreditNoteSyncMixin
from ._customers import CustomerSyncMixin
from ._invoices import InvoiceSyncMixin
from ._payments import PaymentSyncMixin
from ._reconciliation import ReconciliationMixin
from ._types import FullSyncResult

logger = logging.getLogger(__name__)


class SplynxSyncService(
    BaseSyncMixin,
    BankMappingMixin,
    CustomerSyncMixin,
    InvoiceSyncMixin,
    PaymentSyncMixin,
    AllocationMixin,
    CreditNoteSyncMixin,
    ReconciliationMixin,
):
    """Service for syncing data from Splynx to Kxmeleon ERP.

    Syncs:
    - Customers -> AR Customers
    - Invoices -> AR Invoices
    - Payments -> AR Receipts (tracked via correlation_id)
    - Credit Notes -> AR Invoices (type=CREDIT_NOTE)
    """

    def __init__(
        self,
        db: Session,
        organization_id: UUID,
        ar_control_account_id: UUID,
        default_revenue_account_id: UUID | None = None,
        config: SplynxConfig | None = None,
        bank_name_mapping: dict[str, str | None] | None = None,
    ) -> None:
        super().__init__(
            db=db,
            organization_id=organization_id,
            ar_control_account_id=ar_control_account_id,
            default_revenue_account_id=default_revenue_account_id,
            config=config,
            bank_name_mapping=bank_name_mapping,
        )

    def sync_all(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        created_by_user_id: UUID | None = None,
    ) -> FullSyncResult:
        """Sync all entity types from Splynx.

        Syncs in order: customers, invoices, payments, credit_notes.
        """
        start_time = time.time()

        logger.info(
            "Starting full Splynx sync from %s to %s",
            date_from or "beginning",
            date_to or "now",
        )

        customers_result = self.sync_customers(
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
        )
        invoices_result = self.sync_invoices(
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
        )
        payments_result = self.sync_payments(
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
        )
        credit_notes_result = self.sync_credit_notes(
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
        )

        self.post_unposted_payments()

        ledger_result: dict[str, Any] = self.resolve_payment_invoices_from_ledger(
            date_from=date_from,
            date_to=date_to,
        )

        duration = time.time() - start_time
        total_errors = (
            len(customers_result.errors)
            + len(invoices_result.errors)
            + len(payments_result.errors)
            + len(credit_notes_result.errors)
            + len(ledger_result.get("errors", []))
        )

        result = FullSyncResult(
            customers=customers_result,
            invoices=invoices_result,
            payments=payments_result,
            credit_notes=credit_notes_result,
            ledger_resolution=ledger_result,
            total_errors=total_errors,
            duration_seconds=round(duration, 2),
        )

        logger.info(
            "Full Splynx sync completed in %.2fs with %d errors",
            duration,
            total_errors,
        )

        return result
