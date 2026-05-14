from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.people.recruit import JobOpeningStatus, OfferStatus
from app.services.people.recruit.recruit_service import (
    RecruitmentService,
    RecruitmentServiceError,
)
from app.services.people.recruit.web.job_opening_web import JobOpeningWebService


def test_job_opening_input_accepts_position_id() -> None:
    position_id = uuid.uuid4()
    payload = JobOpeningWebService.build_job_opening_input(
        {
            "job_code": "ENG-001",
            "job_title": "Backend Engineer",
            "position_id": str(position_id),
            "employment_type": "FULL_TIME",
            "number_of_positions": "1",
        }
    )

    assert payload["position_id"] == position_id
    assert payload["reports_to_id"] is None


def test_convert_to_employee_rejects_filled_linked_position() -> None:
    org_id = uuid.uuid4()
    position_id = uuid.uuid4()
    offer = SimpleNamespace(
        offer_id=uuid.uuid4(),
        organization_id=org_id,
        applicant_id=uuid.uuid4(),
        job_opening_id=uuid.uuid4(),
        status=OfferStatus.ACCEPTED,
    )
    applicant = SimpleNamespace(
        applicant_id=offer.applicant_id,
        email="ada.candidate@example.com",
    )
    opening = SimpleNamespace(
        job_opening_id=offer.job_opening_id,
        position_id=position_id,
    )
    db = MagicMock()
    db.scalar.side_effect = [offer, applicant, uuid.uuid4()]
    db.get.return_value = opening

    with pytest.raises(RecruitmentServiceError, match="already filled"):
        RecruitmentService(db).convert_to_employee(
            org_id,
            offer.offer_id,
            date_of_joining=date(2026, 6, 15),
            create_onboarding=False,
            send_welcome_email=False,
        )

    assert db.scalar.call_count == 3


def test_create_job_opening_rejects_filled_position() -> None:
    org_id = uuid.uuid4()
    position_id = uuid.uuid4()
    db = MagicMock()
    db.scalar.side_effect = [position_id, uuid.uuid4()]

    with pytest.raises(RecruitmentServiceError, match="already filled"):
        RecruitmentService(db).create_job_opening(
            org_id,
            job_code="JOB-001",
            job_title="Backend Engineer",
            position_id=position_id,
            currency_code="NGN",
        )

    db.add.assert_not_called()


def test_job_opening_marked_filled_when_conversion_reaches_target() -> None:
    opening = SimpleNamespace(
        positions_filled=1,
        number_of_positions=1,
        status=JobOpeningStatus.OPEN,
    )

    RecruitmentService._sync_job_opening_fill_status(opening)

    assert opening.status == JobOpeningStatus.FILLED
