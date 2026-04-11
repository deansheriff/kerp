from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.models.finance.ar.customer_payment import PaymentMethod
from app.services.splynx.client import SplynxPaymentMethod

logger = logging.getLogger(__name__)


class BankMappingMixin:
    """Payment method and bank account mapping logic."""

    # Provided by BaseSyncMixin at runtime
    db: Any
    organization_id: UUID
    client: Any
    _payment_method_cache: dict[int, SplynxPaymentMethod]
    _bank_account_mapping: dict[int, UUID]
    _bank_name_mapping: dict[str, str | None]
    _default_bank_account_cache: dict[str, UUID]

    def _load_payment_methods(self) -> None:
        """Load payment methods from Splynx and build bank mapping."""
        if self._payment_method_cache:
            return

        methods = self.client.get_payment_methods()
        for m in methods:
            self._payment_method_cache[m.id] = m

        # Primary: via Splynx bank account IDs (authoritative)
        self._build_bank_account_mapping_from_splynx_bank_ids()
        # Fallback: name-based fuzzy matching for remaining
        self._build_bank_account_mapping()

    def _build_bank_account_mapping_from_splynx_bank_ids(
        self,
    ) -> None:
        """Map payment methods to ERP bank accounts via Splynx bank IDs.

        Uses Splynx ``accounting_bank_account_id`` to match against ERP
        bank accounts by name.
        """
        from app.models.finance.banking.bank_account import BankAccount

        needed_bank_ids = {
            m.accounting_bank_account_id
            for m in self._payment_method_cache.values()
            if m.accounting_bank_account_id
        }
        if not needed_bank_ids:
            return

        try:
            splynx_bank_accounts = self.client.get_bank_accounts()
        except Exception:
            logger.warning(
                "Could not fetch Splynx bank accounts -- "
                "falling back to name-based mapping"
            )
            return

        splynx_banks = {ba.id: ba for ba in splynx_bank_accounts}

        erp_accounts = list(
            self.db.scalars(
                select(BankAccount).where(
                    BankAccount.organization_id == self.organization_id,
                    BankAccount.status == "active",
                )
            ).all()
        )

        def _norm(value: str | None) -> str:
            if not value:
                return ""
            return re.sub(r"[^a-z0-9]+", "", value.lower())

        erp_search: list[tuple[UUID, str]] = []
        for acct in erp_accounts:
            parts = [
                acct.bank_name,
                acct.account_name,
                acct.account_number,
            ]
            corpus = " ".join(p for p in (_norm(p) for p in parts) if p)
            erp_search.append((acct.bank_account_id, corpus))

        mapped = 0
        for method_id, method in self._payment_method_cache.items():
            if method_id in self._bank_account_mapping:
                continue
            if not method.accounting_bank_account_id:
                continue
            splynx_bank = splynx_banks.get(method.accounting_bank_account_id)
            if not splynx_bank:
                continue

            splynx_bank_norm = _norm(splynx_bank.name)
            for erp_id, erp_corpus in erp_search:
                if splynx_bank_norm and splynx_bank_norm in erp_corpus:
                    self._bank_account_mapping[method_id] = erp_id
                    logger.debug(
                        "Mapped Splynx method '%s' via bank "
                        "account '%s' (Splynx bank ID %d)",
                        method.name,
                        splynx_bank.name,
                        splynx_bank.id,
                    )
                    mapped += 1
                    break

        if mapped:
            logger.info(
                "Mapped %d payment methods via Splynx bank account IDs",
                mapped,
            )

    def _build_bank_account_mapping(self) -> None:
        """Build mapping from Splynx method names to ERP bank accounts.

        Matches by partial name using ``self._bank_name_mapping``.
        Only processes methods not already mapped by the bank-ID approach.
        """
        from app.models.finance.banking.bank_account import BankAccount

        def _normalize_text(value: str | None) -> str:
            if not value:
                return ""
            return re.sub(r"[^a-z0-9]+", "", value.lower())

        def _matches_account_pattern(pattern: str, account_search: str) -> bool:
            if pattern in account_search:
                return True
            m = re.fullmatch(r"([a-z]+)(\d+)", pattern)
            if m:
                return m.group(1) in account_search and m.group(2) in account_search
            return False

        stmt = (
            select(BankAccount)
            .where(
                BankAccount.organization_id == self.organization_id,
                BankAccount.status == "active",
            )
            .order_by(
                BankAccount.is_primary.desc(),
                BankAccount.created_at.asc(),
            )
        )
        accounts = self.db.scalars(stmt).all()

        account_candidates: list[tuple[UUID, str]] = []
        for acct in accounts:
            search_parts = [
                acct.bank_name,
                acct.account_name,
                f"{acct.bank_name} {acct.account_name}",
                acct.account_number,
            ]
            if acct.account_number and len(acct.account_number) >= 4:
                search_parts.append(acct.account_number[-4:])

            normalized_search = " ".join(
                part for part in (_normalize_text(p) for p in search_parts) if part
            )
            account_candidates.append((acct.bank_account_id, normalized_search))

        normalized_rules = {
            _normalize_text(splynx_pattern): (
                _normalize_text(erp_pattern) if erp_pattern else None
            )
            for splynx_pattern, erp_pattern in (self._bank_name_mapping.items())
        }

        for method_id, method in self._payment_method_cache.items():
            if method_id in self._bank_account_mapping:
                continue
            normalized_method_name = _normalize_text(method.name)

            for splynx_pattern, erp_pattern in normalized_rules.items():
                if not splynx_pattern or splynx_pattern not in normalized_method_name:
                    continue
                if not erp_pattern:
                    break

                for bank_account_id, account_search in account_candidates:
                    if _matches_account_pattern(erp_pattern, account_search):
                        self._bank_account_mapping[method_id] = bank_account_id
                        logger.debug(
                            "Mapped Splynx method '%s' via pattern '%s'",
                            method.name,
                            splynx_pattern,
                        )
                        break
                break

        mapped_count = len(self._bank_account_mapping)
        total_count = len(self._payment_method_cache)
        logger.info(
            "Built bank account mapping: %d of %d payment methods mapped",
            mapped_count,
            total_count,
        )

        if mapped_count < total_count:
            unmapped = [
                f"'{method.name}' (id={mid})"
                for mid, method in (self._payment_method_cache.items())
                if mid not in self._bank_account_mapping
            ]
            logger.warning(
                "Unmapped Splynx payment methods (will use "
                "default bank account, may cause reconciliation "
                "mismatches): %s. Add entries to "
                "DEFAULT_BANK_NAME_MAPPING to fix.",
                ", ".join(unmapped),
            )

    def _get_default_bank_account(self, currency_code: str) -> UUID | None:
        """Get the org's default active bank account for a currency."""
        from app.models.finance.banking.bank_account import BankAccount

        code = (currency_code or settings.default_functional_currency_code).upper()
        cached = self._default_bank_account_cache.get(code)
        if cached:
            return cached

        stmt = (
            select(BankAccount.bank_account_id)
            .where(
                BankAccount.organization_id == self.organization_id,
                BankAccount.currency_code == code,
                BankAccount.status == "active",
            )
            .order_by(
                BankAccount.is_primary.desc(),
                BankAccount.created_at.asc(),
            )
        )
        bank_account_id = self.db.scalar(stmt)
        if bank_account_id:
            self._default_bank_account_cache[code] = bank_account_id
        return bank_account_id

    def _get_bank_account_for_payment(
        self, payment_type: int, currency_code: str
    ) -> UUID | None:
        """Get ERP bank account ID for a Splynx payment type."""
        self._load_payment_methods()
        mapped = self._bank_account_mapping.get(payment_type)
        if mapped:
            return mapped
        return self._get_default_bank_account(currency_code)

    def _get_payment_method_name(self, payment_type: int) -> str:
        """Get payment method name for display."""
        self._load_payment_methods()
        method = self._payment_method_cache.get(payment_type)
        return method.name if method else f"Method {payment_type}"

    def _map_payment_method(self, payment_type: int) -> PaymentMethod:
        """Map Splynx payment type to ERP PaymentMethod enum."""
        self._load_payment_methods()
        method = self._payment_method_cache.get(payment_type)
        if not method:
            return PaymentMethod.BANK_TRANSFER

        name_lower = method.name.lower()
        if "cash" in name_lower:
            return PaymentMethod.CASH
        elif (
            "paystack" in name_lower
            or "flutterwave" in name_lower
            or "flutter wave" in name_lower
            or "fluterwave" in name_lower
        ):
            return PaymentMethod.CARD
        elif "remita" in name_lower:
            return PaymentMethod.DIRECT_DEBIT
        else:
            return PaymentMethod.BANK_TRANSFER
