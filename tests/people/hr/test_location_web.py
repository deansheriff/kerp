from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.services.people.hr.web.location_web import LocationWebService
from app.web.deps import WebAuthContext


def _make_post_request(form: dict[str, str]) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/people/hr/locations/new",
            "headers": [],
        }
    )
    request.state.csrf_form = form
    return request


def _make_get_request(query_string: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/people/hr/locations/new",
            "query_string": query_string,
            "headers": [],
        }
    )


def _auth(*, organization_id, roles: list[str]) -> WebAuthContext:
    return WebAuthContext(
        is_authenticated=True,
        person_id=uuid4(),
        organization_id=organization_id,
        roles=roles,
        scopes=["hr:access"],
    )


def _valid_branch_form(**overrides: str) -> dict[str, str]:
    form = {
        "location_code": "LAG",
        "location_name": "Lagos Branch",
        "location_type": "BRANCH",
        "is_active": "true",
        "geofence_enabled": "true",
    }
    form.update(overrides)
    return form


@pytest.mark.asyncio
async def test_admin_create_location_uses_selected_organization(monkeypatch):
    admin_org_id = uuid4()
    target_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeOrganizationService:
        def __init__(self, db, organization_id):
            captured["organization_id"] = organization_id

        def create_location(self, **kwargs):
            captured["payload"] = kwargs
            return SimpleNamespace()

    db = SimpleNamespace(commit=lambda: captured.setdefault("committed", True))
    monkeypatch.setattr(
        "app.services.people.hr.web.location_web.OrganizationService",
        FakeOrganizationService,
    )

    response = await LocationWebService.create_location_response(
        request=_make_post_request(
            _valid_branch_form(organization_id=str(target_org_id))
        ),
        auth=_auth(organization_id=admin_org_id, roles=["admin"]),
        db=db,
    )

    assert response.status_code == 303
    assert captured["organization_id"] == target_org_id
    assert captured["payload"]["location_code"] == "LAG"
    assert f"organization_id={target_org_id}" in response.headers["location"]
    assert captured["committed"] is True


@pytest.mark.asyncio
async def test_non_admin_create_location_ignores_posted_organization(monkeypatch):
    user_org_id = uuid4()
    posted_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeOrganizationService:
        def __init__(self, db, organization_id):
            captured["organization_id"] = organization_id

        def create_location(self, **kwargs):
            captured["payload"] = kwargs
            return SimpleNamespace()

    db = SimpleNamespace(commit=lambda: captured.setdefault("committed", True))
    monkeypatch.setattr(
        "app.services.people.hr.web.location_web.OrganizationService",
        FakeOrganizationService,
    )

    response = await LocationWebService.create_location_response(
        request=_make_post_request(
            _valid_branch_form(organization_id=str(posted_org_id))
        ),
        auth=_auth(organization_id=user_org_id, roles=["hr_manager"]),
        db=db,
    )

    assert response.status_code == 303
    assert captured["organization_id"] == user_org_id
    assert captured["organization_id"] != posted_org_id
    assert response.headers["location"] == (
        "/people/hr/locations?success=Record+saved+successfully"
    )


def test_new_location_form_shows_admin_organization_picker(monkeypatch):
    selected_org_id = uuid4()
    other_org_id = uuid4()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        LocationWebService,
        "_active_organization_options",
        staticmethod(
            lambda db: [
                {"id": str(selected_org_id), "name": "Selected Org"},
                {"id": str(other_org_id), "name": "Other Org"},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.people.hr.web.location_web.base_context",
        lambda request, auth, title, active: {"title": title, "active_page": active},
    )
    monkeypatch.setattr(
        "app.services.people.hr.web.location_web.templates.TemplateResponse",
        lambda request, template_name, context: captured.setdefault(
            "response",
            SimpleNamespace(
                status_code=200,
                template_name=template_name,
                context=context,
            ),
        ),
    )

    response = LocationWebService.new_location_form_response(
        request=_make_get_request(f"organization_id={selected_org_id}".encode()),
        auth=_auth(organization_id=other_org_id, roles=["admin"]),
        db=SimpleNamespace(),
    )

    assert response.status_code == 200
    assert response.context["show_organization_field"] is True
    assert response.context["selected_organization_id"] == str(selected_org_id)
    assert response.context["organization_options"][0]["name"] == "Selected Org"
