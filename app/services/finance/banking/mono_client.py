"""
Mono API Client.

Handles all HTTP communication with the Mono Connect API for bank account
linking and transaction retrieval.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

import httpx

from app.metrics import categorize_http_status, observe_integration_request

logger = logging.getLogger(__name__)

MONO_BASE_URL = "https://api.withmono.com"


class MonoError(Exception):
    """Mono API error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class MonoConfig:
    """Configuration for Mono API."""

    secret_key: str = ""
    public_key: str = ""
    webhook_secret: str = ""


@dataclass
class MonoTransaction:
    """A single transaction record from Mono."""

    id: str
    narration: str
    amount: int  # in minor currency units (kobo for NGN)
    type: str  # "debit" or "credit"
    balance: int | None  # running balance in minor units, may be null
    date: str  # ISO 8601 timestamp
    category: str | None = None

    @property
    def amount_major(self) -> Decimal:
        """Amount in major currency units (Naira)."""
        return Decimal(self.amount) / Decimal("100")

    @property
    def balance_major(self) -> Decimal | None:
        """Balance in major currency units (Naira)."""
        if self.balance is None:
            return None
        return Decimal(self.balance) / Decimal("100")


@dataclass
class MonoAccountIdentity:
    """Account holder identity from Mono."""

    full_name: str
    email: str | None = None
    phone: str | None = None
    bvn: str | None = None
    account_number: str | None = None
    institution_name: str | None = None


@dataclass
class MonoExchangeResult:
    """Result from exchanging a Mono Connect widget code."""

    account_id: str


@dataclass
class MonoTransactionPage:
    """A page of transactions from Mono."""

    transactions: list[MonoTransaction] = field(default_factory=list)
    total: int = 0
    page: int = 1
    has_next: bool = False
    next_url: str | None = None


class MonoClient:
    """
    HTTP client for Mono Connect API.

    Handles token exchange, transaction retrieval, and webhook verification.
    """

    def __init__(self, config: MonoConfig, timeout: float = 30.0):
        self.config = config
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def __enter__(self) -> MonoClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=MONO_BASE_URL,
                headers={
                    "mono-sec-key": self.config.secret_key,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Mono API."""
        started_at = time.perf_counter()
        metric_status = "unknown"
        try:
            response = self._get_client().request(
                method=method,
                url=path,
                params=params,
                json=json,
            )
            metric_status = categorize_http_status(response.status_code)
            if response.status_code >= 400:
                body = response.json() if response.content else {}
                msg = body.get("message", response.text[:200])
                raise MonoError(
                    f"Mono API error: {msg}",
                    status_code=response.status_code,
                )
            return cast(dict[str, Any], response.json())
        except MonoError:
            observe_integration_request(
                "mono",
                operation,
                metric_status,
                max(time.perf_counter() - started_at, 0.0),
            )
            raise
        except httpx.RequestError as exc:
            observe_integration_request(
                "mono",
                operation,
                "request_error",
                max(time.perf_counter() - started_at, 0.0),
            )
            raise MonoError(f"Mono request failed: {exc}") from exc
        finally:
            if metric_status == "success":
                observe_integration_request(
                    "mono",
                    operation,
                    metric_status,
                    max(time.perf_counter() - started_at, 0.0),
                )

    # ------------------------------------------------------------------
    # Account linking
    # ------------------------------------------------------------------

    def exchange_token(self, code: str) -> MonoExchangeResult:
        """
        Exchange a Mono Connect widget authorization code for an account ID.

        The code expires after 10 minutes. The returned account_id is permanent
        unless unlinked via the API.

        Args:
            code: Authorization code from Mono Connect widget onSuccess callback.

        Returns:
            MonoExchangeResult with the permanent account_id.
        """
        response = self._request(
            "POST",
            "/v2/accounts/auth",
            operation="exchange_token",
            json={"code": code},
        )
        data = response.get("data", {})
        account_id = data.get("id", "")
        if not account_id:
            raise MonoError("No account ID returned from Mono")
        logger.info("Mono token exchanged successfully, account_id=%s", account_id)
        return MonoExchangeResult(account_id=account_id)

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def get_transactions(
        self,
        account_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
        narration: str | None = None,
        type: str | None = None,
        limit: int = 100,
        paginate: bool = True,
    ) -> MonoTransactionPage:
        """
        Fetch transactions for a linked account.

        Args:
            account_id: Mono account ID from exchange_token.
            start: Start date in DD-MM-YYYY format.
            end: End date in DD-MM-YYYY format.
            narration: Filter by narration text.
            type: Filter by "debit" or "credit".
            limit: Number of transactions per page.
            paginate: Whether to paginate results.

        Returns:
            MonoTransactionPage with transactions and pagination info.
        """
        params: dict[str, Any] = {"limit": limit, "paginate": paginate}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if narration:
            params["narration"] = narration
        if type:
            params["type"] = type

        response = self._request(
            "GET",
            f"/v2/accounts/{account_id}/transactions",
            operation="get_transactions",
            params=params,
        )

        data = response.get("data", [])
        meta = response.get("meta", {})

        transactions = [
            MonoTransaction(
                id=txn["id"],
                narration=txn.get("narration", ""),
                amount=txn.get("amount", 0),
                type=txn.get("type", "debit"),
                balance=txn.get("balance"),
                date=txn.get("date", ""),
                category=txn.get("category"),
            )
            for txn in data
        ]

        return MonoTransactionPage(
            transactions=transactions,
            total=meta.get("total", len(transactions)),
            page=meta.get("page", 1),
            has_next=meta.get("next") is not None,
            next_url=meta.get("next"),
        )

    def get_all_transactions(
        self,
        account_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[MonoTransaction]:
        """
        Fetch all transactions for a date range, handling pagination.

        Args:
            account_id: Mono account ID.
            start: Start date in DD-MM-YYYY format.
            end: End date in DD-MM-YYYY format.
            limit: Page size.

        Returns:
            Complete list of MonoTransaction objects.
        """
        all_transactions: list[MonoTransaction] = []
        params: dict[str, Any] = {"limit": limit, "paginate": True}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        path = f"/v2/accounts/{account_id}/transactions"

        while True:
            response = self._request(
                "GET",
                path,
                operation="get_transactions",
                params=params,
            )

            data = response.get("data", [])
            meta = response.get("meta", {})

            for txn in data:
                all_transactions.append(
                    MonoTransaction(
                        id=txn["id"],
                        narration=txn.get("narration", ""),
                        amount=txn.get("amount", 0),
                        type=txn.get("type", "debit"),
                        balance=txn.get("balance"),
                        date=txn.get("date", ""),
                        category=txn.get("category"),
                    )
                )

            next_url = meta.get("next")
            if not next_url or not data:
                break

            # For subsequent pages, use the next URL directly
            # Clear params since the next URL contains them
            path = next_url.replace(MONO_BASE_URL, "")
            params = {}

        return all_transactions

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    def get_account_identity(self, account_id: str) -> MonoAccountIdentity:
        """
        Get identity information for a linked account.

        Args:
            account_id: Mono account ID.

        Returns:
            MonoAccountIdentity with account holder details.
        """
        response = self._request(
            "GET",
            f"/v2/accounts/{account_id}/identity",
            operation="get_identity",
        )
        data = response.get("data", {})
        return MonoAccountIdentity(
            full_name=data.get("full_name", ""),
            email=data.get("email"),
            phone=data.get("phone"),
            bvn=data.get("bvn"),
            account_number=data.get("account_number"),
            institution_name=data.get("meta", {}).get("institution_name"),
        )

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    def verify_webhook(self, header_secret: str) -> bool:
        """
        Verify a Mono webhook request by comparing the header secret.

        Mono uses a simple string comparison (not HMAC). The
        ``mono-webhook-secret`` header value must match the webhook secret
        configured in the Mono dashboard.

        Args:
            header_secret: Value of the ``mono-webhook-secret`` request header.

        Returns:
            True if the secret matches.
        """
        import hmac

        return hmac.compare_digest(header_secret, self.config.webhook_secret)
