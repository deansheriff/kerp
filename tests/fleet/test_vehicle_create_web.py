from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.services.fleet.web.fleet_web import FleetWebService
from app.web.deps import WebAuthContext


def _request(form: dict[str, str]) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/fleet/vehicles/new",
            "headers": [],
        }
    )
    request.state.csrf_form = form
    return request


def _auth(organization_id):
    return WebAuthContext(
        is_authenticated=True,
        person_id=uuid4(),
        organization_id=organization_id,
        roles=["fleet_manager"],
        scopes=["fleet:access"],
    )


def _vehicle_form(**overrides: str) -> dict[str, str]:
    form = {
        "registration_number": "ABC-123",
        "make": "Toyota",
        "model": "Corolla",
        "year": "2024",
        "vehicle_type": "sedan",
        "fuel_type": "petrol",
        "ownership_type": "owned",
        "seating_capacity": "5",
        "current_odometer_km": "0",
    }
    form.update(overrides)
    return form


@pytest.mark.asyncio
async def test_create_vehicle_redirects_to_list_after_success(monkeypatch):
    org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeVehicleService:
        def __init__(self, db, organization_id):
            captured["organization_id"] = organization_id

        def create(self, data):
            captured["data"] = data
            return SimpleNamespace(vehicle_id=uuid4())

    db = SimpleNamespace(commit=lambda: captured.setdefault("committed", True))
    monkeypatch.setattr("app.services.fleet.vehicle_service.VehicleService", FakeVehicleService)

    response = await FleetWebService(db).create_vehicle_response(
        _request(_vehicle_form()),
        org_id,
        uuid4(),
        db,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/fleet/vehicles?success=Vehicle+created+successfully"
    )
    assert captured["organization_id"] == org_id
    assert captured["data"].registration_number == "ABC-123"
    assert captured["committed"] is True


@pytest.mark.asyncio
async def test_create_vehicle_rolls_back_and_returns_to_form_on_failure(monkeypatch):
    org_id = uuid4()
    captured: dict[str, object] = {}

    class FakeVehicleService:
        def __init__(self, db, organization_id):
            pass

        def create(self, data):
            raise RuntimeError("vehicle duplicate")

    db = SimpleNamespace(
        commit=lambda: captured.setdefault("committed", True),
        rollback=lambda: captured.setdefault("rolled_back", True),
    )
    monkeypatch.setattr("app.services.fleet.vehicle_service.VehicleService", FakeVehicleService)

    response = await FleetWebService(db).create_vehicle_response(
        _request(_vehicle_form()),
        org_id,
        uuid4(),
        db,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/fleet/vehicles/new?error=vehicle%20duplicate"
    )
    assert captured["rolled_back"] is True
    assert "committed" not in captured


@pytest.mark.asyncio
async def test_create_fuel_log_uses_linked_employee_id(monkeypatch):
    org_id = uuid4()
    person_id = uuid4()
    employee_id = uuid4()
    captured: dict[str, object] = {}

    class FakeFuelService:
        def __init__(self, db, organization_id):
            captured["organization_id"] = organization_id

        def create(self, data):
            captured["data"] = data

    class FakeDb:
        def get(self, model, pk):
            return None

        def scalar(self, stmt):
            captured["employee_lookup"] = str(stmt)
            return employee_id

        def commit(self):
            captured["committed"] = True

        def rollback(self):
            captured["rolled_back"] = True

    monkeypatch.setattr(
        "app.services.fleet.web.fleet_web.FuelService",
        FakeFuelService,
    )
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=person_id,
        organization_id=org_id,
        roles=["fleet_manager"],
        scopes=["fleet:access"],
    )

    response = await FleetWebService(FakeDb()).create_entity_response(
        _request(
            {
                "vehicle_id": str(uuid4()),
                "log_date": "2026-07-06",
                "fuel_type": "PETROL",
                "quantity_liters": "40",
                "price_per_liter": "850",
                "total_cost": "34000",
                "odometer_reading": "1000",
            }
        ),
        auth,
        FakeDb(),
        "fuel",
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/fleet/fuel"
    assert captured["organization_id"] == org_id
    assert captured["data"].employee_id == employee_id
    assert captured["data"].employee_id != person_id
    assert captured["committed"] is True
