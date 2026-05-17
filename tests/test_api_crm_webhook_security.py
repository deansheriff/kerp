import asyncio
import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.api import crm as crm_api


class _FakeRequest:
    def __init__(self, payload: bytes = b"{}") -> None:
        self._payload = payload

    async def body(self) -> bytes:
        return self._payload

    async def json(self) -> dict[str, str]:
        import json

        return json.loads(self._payload.decode("utf-8"))


class _FakeCRMClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_verify_crm_signature_returns_false_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(crm_api.settings, "crm_webhook_secret", None, raising=False)

    assert crm_api.verify_crm_signature(b'{"event":"ticket.created"}', "any-value") is (
        False
    )


def test_verify_crm_signature_validates_hmac_sha256(monkeypatch):
    payload = b'{"event":"ticket.updated","id":"crm-123"}'
    secret = "webhook-secret"
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        crm_api.settings,
        "crm_webhook_secret",
        secret,
        raising=False,
    )

    assert crm_api.verify_crm_signature(payload, signature) is True
    assert crm_api.verify_crm_signature(payload, "invalid") is False


def test_crm_webhook_returns_503_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(crm_api.settings, "crm_webhook_secret", None, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            crm_api.crm_webhook(
                request=_FakeRequest(),
                x_crm_signature="any-signature",
                db=None,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "CRM webhook authentication is not configured"


def test_crm_webhook_primes_both_tenant_layers_before_processing(monkeypatch):
    payload = b'{"event":"ignored","type":"unknown"}'
    secret = "webhook-secret"
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    org_id = "11111111-1111-1111-1111-111111111111"
    db = object()
    calls = []

    monkeypatch.setattr(crm_api.settings, "crm_webhook_secret", secret, raising=False)
    monkeypatch.setattr(
        crm_api.settings,
        "default_organization_id",
        org_id,
        raising=False,
    )
    monkeypatch.setattr(
        crm_api,
        "prime_tenant_context",
        lambda session, organization_id: calls.append((session, organization_id)),
    )
    monkeypatch.setattr("app.services.crm.CRMClient", _FakeCRMClient)

    response = asyncio.run(
        crm_api.crm_webhook(
            request=_FakeRequest(payload),
            x_crm_signature=signature,
            db=db,
        )
    )

    assert response.status == "ignored"
    assert calls == [(db, crm_api.UUID(org_id))]
