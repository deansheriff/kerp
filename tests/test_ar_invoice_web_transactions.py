from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.finance.ar.web.invoice_web import InvoiceWebService


@pytest.mark.asyncio
async def test_create_invoice_response_returns_detail_redirect(monkeypatch):
    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value={"customer_id": str(uuid4()), "lines": []})
    auth = SimpleNamespace(organization_id=uuid4(), user_id=uuid4())
    db = MagicMock()
    invoice_id = uuid4()

    monkeypatch.setattr(
        InvoiceWebService,
        "build_invoice_input",
        staticmethod(lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(
        "app.services.finance.ar.web.invoice_web.ar_invoice_service.create_invoice",
        lambda **_kwargs: SimpleNamespace(invoice_id=invoice_id),
    )

    response = await InvoiceWebService().create_invoice_response(request, auth, db)

    assert response["success"] is True
    assert response["invoice_id"] == str(invoice_id)
    assert response["redirect_url"] == f"/finance/ar/invoices/{invoice_id}"


@pytest.mark.asyncio
async def test_update_invoice_response_returns_detail_redirect(monkeypatch):
    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value={"customer_id": str(uuid4()), "lines": []})
    auth = SimpleNamespace(organization_id=uuid4(), user_id=uuid4())
    db = MagicMock()
    invoice_id = uuid4()

    monkeypatch.setattr(
        InvoiceWebService,
        "build_invoice_input",
        staticmethod(lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(
        "app.services.finance.ar.web.invoice_web.ar_invoice_service.update_invoice",
        lambda **_kwargs: SimpleNamespace(invoice_id=invoice_id),
    )

    response = await InvoiceWebService().update_invoice_response(
        request, auth, db, str(invoice_id)
    )

    payload = json.loads(response.body)
    assert payload["success"] is True
    assert payload["invoice_id"] == str(invoice_id)
    assert payload["redirect_url"] == f"/finance/ar/invoices/{invoice_id}"
