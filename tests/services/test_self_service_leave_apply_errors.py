from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.people.leave.leave_service import (
    InsufficientLeaveBalanceError,
    LeaveTypeNotFoundError,
    OverlappingLeaveApplicationError,
)
from app.services.people.self_service_web import SelfServiceWebService


def _make_auth():
    auth = MagicMock()
    auth.organization_id = "00000000-0000-0000-0000-000000000001"
    auth.person_id = "00000000-0000-0000-0000-000000000002"
    return auth


def test_leave_apply_raises_422_for_insufficient_balance():
    svc = SelfServiceWebService()
    auth = _make_auth()
    db = MagicMock()

    with (
        patch.object(
            svc, "_get_employee_id", return_value="00000000-0000-0000-0000-000000000003"
        ),
        patch("app.services.people.self_service_web.LeaveService") as leave_service,
    ):
        leave_service.return_value.create_application.side_effect = (
            InsufficientLeaveBalanceError(available=1, requested=2)
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.leave_apply_response(
                auth,
                db,
                leave_type_id="00000000-0000-0000-0000-000000000010",
                from_date=date(2026, 4, 7),
                to_date=date(2026, 4, 8),
                half_day=None,
                reason="Vacation",
            )

    assert exc_info.value.status_code == 422
    db.rollback.assert_called_once()


def test_leave_apply_raises_404_for_unknown_leave_type():
    svc = SelfServiceWebService()
    auth = _make_auth()
    db = MagicMock()

    missing_leave_type = "00000000-0000-0000-0000-000000000010"
    with (
        patch.object(
            svc, "_get_employee_id", return_value="00000000-0000-0000-0000-000000000003"
        ),
        patch("app.services.people.self_service_web.LeaveService") as leave_service,
    ):
        leave_service.return_value.create_application.side_effect = (
            LeaveTypeNotFoundError(missing_leave_type)
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.leave_apply_response(
                auth,
                db,
                leave_type_id=missing_leave_type,
                from_date=date(2026, 4, 7),
                to_date=date(2026, 4, 8),
                half_day=None,
                reason="Vacation",
            )

    assert exc_info.value.status_code == 404
    db.rollback.assert_called_once()


def test_leave_apply_allows_conflict_errors_to_propagate_as_409():
    svc = SelfServiceWebService()
    auth = _make_auth()
    db = MagicMock()

    with (
        patch.object(
            svc, "_get_employee_id", return_value="00000000-0000-0000-0000-000000000003"
        ),
        patch("app.services.people.self_service_web.LeaveService") as leave_service,
    ):
        leave_service.return_value.create_application.side_effect = (
            OverlappingLeaveApplicationError(date(2026, 4, 7), date(2026, 4, 8))
        )

        with pytest.raises(OverlappingLeaveApplicationError) as exc_info:
            svc.leave_apply_response(
                auth,
                db,
                leave_type_id="00000000-0000-0000-0000-000000000010",
                from_date=date(2026, 4, 7),
                to_date=date(2026, 4, 8),
                half_day=None,
                reason="Vacation",
            )

    assert exc_info.value.status_code == 409
    db.rollback.assert_called_once()
