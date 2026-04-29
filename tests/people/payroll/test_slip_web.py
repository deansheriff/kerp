from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch
from uuid import uuid4

from app.services.people.payroll.web.slip_web import SlipWebService


def test_post_slip_response_creates_notification_and_queues_email():
    org_id = uuid4()
    user_id = uuid4()
    slip_id = uuid4()
    employee = SimpleNamespace(employee_id=uuid4(), person_id=uuid4())
    slip = SimpleNamespace(
        slip_id=slip_id,
        organization_id=org_id,
        employee=employee,
    )
    auth = SimpleNamespace(organization_id=str(org_id), user_id=str(user_id))
    db = MagicMock()
    db.get.return_value = slip

    with (
        patch(
            "app.services.people.payroll.web.slip_web.PayrollGLAdapter.post_salary_slip"
        ) as mock_post,
        patch(
            "app.services.people.payroll.payroll_notifications.PayrollNotificationService"
        ) as mock_service_cls,
    ):
        mock_service = mock_service_cls.return_value

        response = SlipWebService().post_slip_response(auth, db, str(slip_id))

        assert response.status_code == 303
        assert response.headers["location"] == (
            f"/people/payroll/slips/{slip_id}?saved=1"
        )
        mock_post.assert_called_once()
        db.get.assert_called_once_with(ANY, slip_id)
        mock_service.notify_payslip_posted.assert_called_once_with(
            slip,
            employee,
            queue_email=True,
        )
        db.commit.assert_called_once()
