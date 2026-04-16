from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.finance.ar.customer import Customer
from app.models.finance.ar.external_sync import (
    EntityType,
    ExternalSource,
    ExternalSync,
)
from app.models.finance.ar.invoice import Invoice
from app.models.finance.ar.invoice_line_tax import InvoiceLineTax
from app.models.finance.tax.tax_code import TaxCode, TaxType
from app.services.splynx.client import SplynxClient, SplynxConfig

from ._constants import DEFAULT_BANK_NAME_MAPPING

logger = logging.getLogger(__name__)


class BaseSyncMixin:
    """Core utilities shared by all sync mixins.

    Provides ``__init__``, ``close``, date parsing, hashing, sync tracking,
    tax extraction, and number generation.
    """

    # Prefix for Splynx-sourced records
    SOURCE_PREFIX = "SPLYNX"

    def __init__(
        self,
        db: Session,
        organization_id: UUID,
        ar_control_account_id: UUID,
        default_revenue_account_id: UUID | None = None,
        config: SplynxConfig | None = None,
        bank_name_mapping: dict[str, str | None] | None = None,
    ) -> None:
        self.db = db
        self.organization_id = organization_id
        self.ar_control_account_id = ar_control_account_id
        self.default_revenue_account_id = default_revenue_account_id
        self.config = config or SplynxConfig.from_settings()
        self._client: SplynxClient | None = None
        self._bank_name_mapping = bank_name_mapping or DEFAULT_BANK_NAME_MAPPING

        # Caches
        self._customer_cache: dict[int, UUID] = {}
        self._partner_cache: dict[int, UUID] = {}
        self._payment_method_cache: dict[int, Any] = {}
        self._bank_account_mapping: dict[int, UUID] = {}
        self._default_bank_account_cache: dict[str, UUID] = {}

        # Sales tax code (lazy)
        self._sales_tax_code_resolved: bool = False
        self._sales_tax_code: TaxCode | None = None

        # Sync entity cache
        self._sync_entity_cache: dict[tuple[str, str], UUID | None] = {}

    @property
    def sales_tax_code(self) -> TaxCode | None:
        """Lazy-resolve the org's active VAT sales tax code.

        Returns a detached-safe copy so that ``db.expunge_all()``
        (called every 500 records during batch sync) does not
        invalidate the cached reference.
        """
        if not self._sales_tax_code_resolved:
            live = self._resolve_sales_tax()
            if live is not None:
                # Snapshot scalar attributes into a plain object so the
                # cached reference survives session expunge/rollback.
                from types import SimpleNamespace

                self._sales_tax_code = SimpleNamespace(  # type: ignore[assignment]
                    tax_code_id=live.tax_code_id,
                    tax_code=live.tax_code,
                    tax_name=live.tax_name,
                    tax_rate=live.tax_rate,
                    is_inclusive=live.is_inclusive,
                    is_compound=live.is_compound,
                    tax_collected_account_id=live.tax_collected_account_id,
                    tax_paid_account_id=live.tax_paid_account_id,
                )
            self._sales_tax_code_resolved = True
        return self._sales_tax_code

    @property
    def client(self) -> SplynxClient:
        """Lazy-initialize Splynx client."""
        if self._client is None:
            self._client = SplynxClient(self.config)
        return self._client

    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None

    # -----------------------------------------------------------------
    # Tax extraction
    # -----------------------------------------------------------------

    def _resolve_sales_tax(self) -> TaxCode | None:
        """Look up the org's active VAT/GST sales tax code."""
        today = date.today()
        stmt = (
            select(TaxCode)
            .where(
                TaxCode.organization_id == self.organization_id,
                TaxCode.tax_type == TaxType.VAT,
                TaxCode.applies_to_sales.is_(True),
                TaxCode.is_active.is_(True),
                TaxCode.effective_from <= today,
                or_(
                    TaxCode.effective_to.is_(None),
                    TaxCode.effective_to >= today,
                ),
            )
            .order_by(TaxCode.effective_from.desc())
            .limit(1)
        )
        tax_code = self.db.scalar(stmt)
        if tax_code:
            logger.info(
                "Splynx sync using sales tax code '%s' (rate=%s, inclusive=%s)",
                tax_code.tax_code,
                tax_code.tax_rate,
                tax_code.is_inclusive,
            )
        else:
            logger.warning(
                "No active VAT sales tax code found for org %s -- "
                "invoices will be synced without tax extraction",
                self.organization_id,
            )
        return tax_code

    def _extract_tax(self, total: Decimal) -> tuple[Decimal, Decimal]:
        """Extract subtotal and tax from a total amount."""
        tc = self.sales_tax_code
        if not tc or tc.tax_rate == Decimal("0"):
            return total, Decimal("0")

        if tc.is_inclusive:
            divisor = Decimal("1") + tc.tax_rate
            tax_amount = (total * tc.tax_rate / divisor).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            subtotal = total - tax_amount
        else:
            subtotal = total
            tax_amount = (total * tc.tax_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        return subtotal, tax_amount

    def _create_line_tax_record(
        self,
        line_id: UUID,
        base_amount: Decimal,
        tax_amount: Decimal,
    ) -> None:
        """Create an InvoiceLineTax audit record for a synced line."""
        tc = self.sales_tax_code
        if not tc or tax_amount == Decimal("0"):
            return
        line_tax = InvoiceLineTax(
            line_id=line_id,
            tax_code_id=tc.tax_code_id,
            base_amount=base_amount,
            tax_rate=tc.tax_rate,
            tax_amount=tax_amount,
            is_inclusive=tc.is_inclusive,
            sequence=1,
        )
        self.db.add(line_tax)

    # -----------------------------------------------------------------
    # Number generators
    # -----------------------------------------------------------------

    def _make_customer_code(self, splynx_id: int) -> str:
        """Generate customer code from Splynx ID."""
        return f"{self.SOURCE_PREFIX}-{splynx_id}"

    def _generate_invoice_number(self, reference_date: date | None = None) -> str:
        """Generate sequential invoice number."""
        from app.models.finance.core_config.numbering_sequence import (
            SequenceType,
        )
        from app.services.finance.common.numbering import (
            SyncNumberingService,
        )

        svc = SyncNumberingService(self.db)
        return svc.generate_next_number(
            self.organization_id, SequenceType.INVOICE, reference_date
        )

    def _generate_payment_number(self, reference_date: date | None = None) -> str:
        """Generate sequential payment number."""
        from app.models.finance.core_config.numbering_sequence import (
            SequenceType,
        )
        from app.services.finance.common.numbering import (
            SyncNumberingService,
        )

        svc = SyncNumberingService(self.db)
        return svc.generate_next_number(
            self.organization_id, SequenceType.PAYMENT, reference_date
        )

    def _generate_credit_note_number(self, reference_date: date | None = None) -> str:
        """Generate sequential credit note number."""
        from app.models.finance.core_config.numbering_sequence import (
            SequenceType,
        )
        from app.services.finance.common.numbering import (
            SyncNumberingService,
        )

        svc = SyncNumberingService(self.db)
        return svc.generate_next_number(
            self.organization_id,
            SequenceType.CREDIT_NOTE,
            reference_date,
        )

    # -----------------------------------------------------------------
    # Date parsing
    # -----------------------------------------------------------------

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string from Splynx."""
        if not date_str:
            return None
        try:
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                logger.warning("Could not parse date: %s", date_str)
                return None

    # -----------------------------------------------------------------
    # Sync tracking
    # -----------------------------------------------------------------

    def _get_synced_entity(
        self,
        entity_type: EntityType,
        external_id: str,
    ) -> UUID | None:
        """Get local entity ID for a synced external entity."""
        stmt = select(ExternalSync.local_entity_id).where(
            ExternalSync.organization_id == self.organization_id,
            ExternalSync.source == ExternalSource.SPLYNX,
            ExternalSync.entity_type == entity_type,
            ExternalSync.external_id == external_id,
        )
        return self.db.scalar(stmt)

    def _record_sync(
        self,
        entity_type: EntityType,
        external_id: str,
        local_entity_id: UUID,
        data_hash: str | None = None,
        external_updated_at: datetime | None = None,
    ) -> None:
        """Record a sync mapping."""
        existing = self._get_synced_entity(entity_type, external_id)
        if existing:
            stmt = select(ExternalSync).where(
                ExternalSync.organization_id == self.organization_id,
                ExternalSync.source == ExternalSource.SPLYNX,
                ExternalSync.entity_type == entity_type,
                ExternalSync.external_id == external_id,
            )
            sync_record = self.db.scalar(stmt)
            if sync_record:
                sync_record.synced_at = datetime.now(tz=UTC)
                sync_record.sync_hash = data_hash
                if external_updated_at:
                    sync_record.external_updated_at = external_updated_at
        else:
            sync_record = ExternalSync(
                organization_id=self.organization_id,
                source=ExternalSource.SPLYNX,
                entity_type=entity_type,
                external_id=external_id,
                local_entity_id=local_entity_id,
                sync_hash=data_hash,
                external_updated_at=external_updated_at,
            )
            self.db.add(sync_record)

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute hash of data for change detection."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:32]

    def _has_changed(
        self,
        entity_type: EntityType,
        external_id: str,
        new_hash: str,
    ) -> bool:
        """Check if entity has changed since last sync."""
        stmt = select(ExternalSync.sync_hash).where(
            ExternalSync.organization_id == self.organization_id,
            ExternalSync.source == ExternalSource.SPLYNX,
            ExternalSync.entity_type == entity_type,
            ExternalSync.external_id == external_id,
        )
        old_hash = self.db.scalar(stmt)
        return old_hash != new_hash

    # -----------------------------------------------------------------
    # Invoice / customer helpers used across mixins
    # -----------------------------------------------------------------

    def _get_existing_customer(self, customer_code: str) -> Customer | None:
        """Get existing customer by code."""
        stmt = select(Customer).where(
            Customer.organization_id == self.organization_id,
            Customer.customer_code == customer_code,
        )
        return self.db.scalar(stmt)

    def _get_existing_invoice(self, invoice_number: str) -> Invoice | None:
        """Get existing invoice by number."""
        stmt = select(Invoice).where(
            Invoice.organization_id == self.organization_id,
            Invoice.invoice_number == invoice_number,
        )
        return self.db.scalar(stmt)

    def _map_invoice_status(self, splynx_status: str, total_due: Decimal) -> Any:
        """Map Splynx invoice status to ERP status."""
        from app.models.finance.ar.invoice import InvoiceStatus

        status_lower = splynx_status.lower()
        if status_lower == "paid" or total_due == Decimal("0"):
            return InvoiceStatus.PAID
        elif status_lower == "partially_paid":
            return InvoiceStatus.PARTIALLY_PAID
        elif status_lower == "unpaid":
            return InvoiceStatus.POSTED
        else:
            return InvoiceStatus.POSTED
