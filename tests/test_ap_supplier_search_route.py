from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.web.deps import WebAuthContext
from app.web.finance.ap import supplier_search


def test_supplier_search_returns_results_for_non_blank_query(monkeypatch):
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=uuid4(),
        organization_id=uuid4(),
        user_name="Test User",
        user_initials="TU",
        roles=["admin"],
    )

    monkeypatch.setattr(
        "app.web.finance.ap.ap_web_service.supplier_typeahead",
        lambda **_kwargs: {"items": [{"ref": str(uuid4()), "label": "SUP-001 - Acme"}]},
    )

    response = supplier_search(q="acme", limit=20, auth=auth, db=SimpleNamespace())

    assert response.status_code == 200
    assert json.loads(response.body)["items"]
