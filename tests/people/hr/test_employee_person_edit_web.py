from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.models.person import Person
from app.services.people.hr.web.employee_web import HRWebService
from app.web.deps import WebAuthContext


def _make_request(form: dict[str, str]) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/people/hr/employees/test/edit",
            "headers": [],
        }
    )
    request.state.csrf_form = form
    return request


def _make_auth(person_id, organization_id, scopes: list[str]) -> WebAuthContext:
    return WebAuthContext(
        is_authenticated=True,
        person_id=person_id,
        organization_id=organization_id,
        roles=["hr_manager"],
        scopes=["hr:access", *scopes],
    )


@pytest.mark.asyncio
async def test_update_employee_response_updates_linked_person_with_people_write(
    db_session, person, monkeypatch
):
    service = HRWebService()
    employee_id = uuid4()
    employee = SimpleNamespace(employee_id=employee_id, person_id=person.id)

    monkeypatch.setattr(
        "app.services.people.hr.web.employee_web.EmployeeService.get_employee",
        lambda self, _employee_id: employee,
    )
    monkeypatch.setattr(
        "app.services.people.hr.web.employee_web.EmployeeService.update_employee",
        lambda self, _employee_id, _data: employee,
    )
    monkeypatch.setattr(
        HRWebService,
        "_update_tax_profile",
        lambda self, *, auth, db, employee, form: None,
    )

    request = _make_request(
        {
            "first_name": "Updated",
            "last_name": "Person",
            "email": f"updated-{uuid4().hex[:8]}@example.com",
            "phone": "+2348000000000",
            "city": "Lagos",
            "country_code": "NG",
        }
    )
    auth = _make_auth(person.id, person.organization_id, ["people:write"])

    response = await service.update_employee_response(
        request=request,
        employee_id=employee_id,
        auth=auth,
        db=db_session,
    )

    db_session.refresh(person)
    assert response.status_code == 303
    assert person.first_name == "Updated"
    assert person.last_name == "Person"
    assert person.phone == "+2348000000000"
    assert person.city == "Lagos"
    assert person.country_code == "NG"
    assert person.email.startswith("updated-")


@pytest.mark.asyncio
async def test_update_employee_response_keeps_linked_person_read_only_without_people_write(
    db_session, person, monkeypatch
):
    service = HRWebService()
    employee_id = uuid4()
    employee = SimpleNamespace(employee_id=employee_id, person_id=person.id)
    original_email = person.email

    monkeypatch.setattr(
        "app.services.people.hr.web.employee_web.EmployeeService.get_employee",
        lambda self, _employee_id: employee,
    )
    monkeypatch.setattr(
        "app.services.people.hr.web.employee_web.EmployeeService.update_employee",
        lambda self, _employee_id, _data: employee,
    )
    monkeypatch.setattr(
        HRWebService,
        "_update_tax_profile",
        lambda self, *, auth, db, employee, form: None,
    )

    request = _make_request(
        {
            "first_name": "Blocked",
            "email": f"blocked-{uuid4().hex[:8]}@example.com",
            "city": "Abuja",
        }
    )
    auth = _make_auth(person.id, person.organization_id, [])

    response = await service.update_employee_response(
        request=request,
        employee_id=employee_id,
        auth=auth,
        db=db_session,
    )

    stored = db_session.get(Person, person.id)
    assert response.status_code == 303
    assert stored is not None
    assert stored.first_name == person.first_name
    assert stored.email == original_email
    assert stored.city is None
