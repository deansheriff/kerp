from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.services.people.attendance import web as attendance_web
from app.web.deps import WebAuthContext


def _request(form: dict[str, str]) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/people/attendance/shifts/new",
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


def _shift_form(**overrides: str) -> dict[str, str]:
    form = {
        "shift_code": "DAY",
        "shift_name": "Day Shift",
        "start_time": "09:00",
        "end_time": "17:00",
        "is_active": "true",
    }
    form.update(overrides)
    return form


@pytest.mark.asyncio
async def test_admin_shift_create_uses_selected_organization(monkeypatch):
    admin_org_id = uuid4()
    target_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeAttendanceService:
        def __init__(self, db):
            captured["db"] = db

        def create_shift_type(self, org_id, **kwargs):
            captured["organization_id"] = org_id
            captured["payload"] = kwargs
            return SimpleNamespace()

    db = SimpleNamespace(commit=lambda: captured.setdefault("committed", True))
    monkeypatch.setattr(attendance_web, "AttendanceService", FakeAttendanceService)

    response = await attendance_web.AttendanceWebService.create_shift_response(
        request=_request(_shift_form(organization_id=str(target_org_id))),
        auth=_auth(organization_id=admin_org_id, roles=["admin"]),
        db=db,
    )

    assert response.status_code == 303
    assert captured["organization_id"] == target_org_id
    assert captured["payload"]["shift_code"] == "DAY"
    assert f"organization_id={target_org_id}" in response.headers["location"]
    assert captured["committed"] is True


@pytest.mark.asyncio
async def test_non_admin_shift_create_ignores_posted_organization(monkeypatch):
    user_org_id = uuid4()
    posted_org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeAttendanceService:
        def __init__(self, db):
            pass

        def create_shift_type(self, org_id, **kwargs):
            captured["organization_id"] = org_id
            return SimpleNamespace()

    db = SimpleNamespace(commit=lambda: captured.setdefault("committed", True))
    monkeypatch.setattr(attendance_web, "AttendanceService", FakeAttendanceService)

    response = await attendance_web.AttendanceWebService.create_shift_response(
        request=_request(_shift_form(organization_id=str(posted_org_id))),
        auth=_auth(organization_id=user_org_id, roles=["hr_manager"]),
        db=db,
    )

    assert response.status_code == 303
    assert captured["organization_id"] == user_org_id
    assert captured["organization_id"] != posted_org_id
    assert "organization_id=" not in response.headers["location"]
