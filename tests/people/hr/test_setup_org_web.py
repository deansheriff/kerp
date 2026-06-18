from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.web.deps import WebAuthContext
from app.web.people.hr import organization as org_routes


def _request(path: str, form: dict[str, str]) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
        }
    )
    request.state.csrf_form = form
    return request


def _auth(*, organization_id, roles: list[str]) -> WebAuthContext:
    return WebAuthContext(
        is_authenticated=True,
        person_id=uuid4(),
        organization_id=organization_id,
        roles=roles,
        scopes=["hr:access"],
    )


@pytest.mark.asyncio
async def test_admin_department_create_uses_selected_organization(monkeypatch):
    admin_org_id = uuid4()
    target_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeOrganizationService:
        def __init__(self, db, organization_id, principal=None):
            captured["organization_id"] = organization_id
            captured["principal"] = principal

        def create_department(self, data):
            captured["data"] = data
            return SimpleNamespace()

    monkeypatch.setattr(org_routes, "OrganizationService", FakeOrganizationService)

    response = await org_routes.create_department(
        request=_request(
            "/people/hr/departments/new",
            {
                "organization_id": str(target_org_id),
                "department_code": "OPS",
                "department_name": "Operations",
                "is_active": "true",
            },
        ),
        auth=_auth(organization_id=admin_org_id, roles=["admin"]),
        db=SimpleNamespace(),
    )

    assert response.status_code == 303
    assert captured["organization_id"] == target_org_id
    assert captured["data"].department_code == "OPS"
    assert f"organization_id={target_org_id}" in response.headers["location"]


@pytest.mark.asyncio
async def test_non_admin_department_create_ignores_posted_organization(monkeypatch):
    user_org_id = uuid4()
    posted_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeOrganizationService:
        def __init__(self, db, organization_id, principal=None):
            captured["organization_id"] = organization_id

        def create_department(self, data):
            captured["data"] = data
            return SimpleNamespace()

    monkeypatch.setattr(org_routes, "OrganizationService", FakeOrganizationService)

    response = await org_routes.create_department(
        request=_request(
            "/people/hr/departments/new",
            {
                "organization_id": str(posted_org_id),
                "department_code": "FIN",
                "department_name": "Finance",
                "is_active": "true",
            },
        ),
        auth=_auth(organization_id=user_org_id, roles=["hr_manager"]),
        db=SimpleNamespace(),
    )

    assert response.status_code == 303
    assert captured["organization_id"] == user_org_id
    assert captured["organization_id"] != posted_org_id
    assert "organization_id=" not in response.headers["location"]


@pytest.mark.asyncio
async def test_admin_designation_create_uses_selected_organization(monkeypatch):
    admin_org_id = uuid4()
    target_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeOrganizationService:
        def __init__(self, db, organization_id):
            captured["organization_id"] = organization_id

        def create_designation(self, data):
            captured["data"] = data
            return SimpleNamespace()

    monkeypatch.setattr(org_routes, "OrganizationService", FakeOrganizationService)

    response = await org_routes.create_designation(
        request=_request(
            "/people/hr/designations/new",
            {
                "organization_id": str(target_org_id),
                "designation_code": "MGR",
                "designation_name": "Manager",
                "is_active": "true",
            },
        ),
        auth=_auth(organization_id=admin_org_id, roles=["admin"]),
        db=SimpleNamespace(),
    )

    assert response.status_code == 303
    assert captured["organization_id"] == target_org_id
    assert captured["data"].designation_code == "MGR"
    assert f"organization_id={target_org_id}" in response.headers["location"]
