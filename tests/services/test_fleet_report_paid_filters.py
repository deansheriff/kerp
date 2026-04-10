from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.models.expense.expense_claim import ExpenseClaimStatus
from app.services.fleet.web.fleet_web import FleetWebService


TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


class _FakeExecuteResult:
    def __init__(
        self,
        *,
        all_result=None,
        one_result=None,
        scalar_one_result=None,
    ):
        self._all_result = all_result if all_result is not None else []
        self._one_result = one_result
        self._scalar_one_result = scalar_one_result

    def all(self):
        return self._all_result

    def one(self):
        return self._one_result

    def scalar_one(self):
        return self._scalar_one_result


class _FakeScalarsResult:
    def __init__(self, values=None):
        self._values = values if values is not None else []

    def all(self):
        return self._values


class _FakeDb:
    def __init__(self):
        self.executed = []
        self.scalars_calls = []

    def get_bind(self):
        return object()

    def execute(self, stmt):
        self.executed.append(stmt)
        stmt_text = str(stmt)
        if "count(expense.expense_claim.claim_id)" in stmt_text:
            return _FakeExecuteResult(
                one_result=SimpleNamespace(
                    claim_count=0,
                    total_amount=Decimal("0"),
                )
            )
        if "count(*)" in stmt_text:
            return _FakeExecuteResult(scalar_one_result=0)
        return _FakeExecuteResult(all_result=[])

    def scalars(self, stmt):
        self.scalars_calls.append(stmt)
        return _FakeScalarsResult([])


class _InspectorStub:
    def has_table(self, name, schema=None):
        return True


class _VehicleServiceStub:
    def __init__(self, db, organization_id):
        self.db = db
        self.organization_id = organization_id

    def list_vehicles(self, params):
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    vehicle_id=uuid4(),
                    registration_number="ABC-123",
                    make="Toyota",
                    model="Hilux",
                )
            ]
        )

    def get_or_raise(self, vehicle_id):
        return SimpleNamespace(
            vehicle_id=vehicle_id,
            registration_number="ABC-123",
            make="Toyota",
            model="Hilux",
            assigned_employee=None,
            assigned_department_name=None,
        )


def test_reports_expenses_context_filters_to_paid_claims(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(
        "app.services.fleet.web.fleet_web.inspect", lambda bind: _InspectorStub()
    )
    monkeypatch.setattr(
        "app.services.fleet.web.fleet_web.VehicleService",
        _VehicleServiceStub,
    )

    service = FleetWebService(db)
    service.reports_expenses_context(TEST_ORG_ID)

    expense_stmt = next(
        stmt
        for stmt in db.executed
        if "expense.expense_claim.vehicle_id" in str(stmt)
        and "count(expense.expense_claim.claim_id)" in str(stmt)
    )

    assert "expense.expense_claim.status = :status_1" in str(expense_stmt)
    assert expense_stmt.compile().params["status_1"] == ExpenseClaimStatus.PAID


def test_reports_expense_vehicle_context_filters_all_queries_to_paid_claims(
    monkeypatch,
):
    db = _FakeDb()
    monkeypatch.setattr(
        "app.services.fleet.web.fleet_web.inspect", lambda bind: _InspectorStub()
    )
    monkeypatch.setattr(
        "app.services.fleet.web.fleet_web.VehicleService",
        _VehicleServiceStub,
    )

    service = FleetWebService(db)
    service.reports_expense_vehicle_context(TEST_ORG_ID, uuid4())

    statements = db.executed + db.scalars_calls
    expense_statements = [
        stmt for stmt in statements if "expense.expense_claim" in str(stmt)
    ]

    assert expense_statements
    for stmt in expense_statements:
        stmt_text = str(stmt)
        params = stmt.compile().params
        status_params = {
            key: value for key, value in params.items() if key.startswith("status_")
        }

        assert "expense.expense_claim.status = :" in stmt_text
        assert ExpenseClaimStatus.PAID in status_params.values()
