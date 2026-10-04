from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.people.perf.web.perf_web import PerfWebService


@pytest.mark.asyncio
async def test_progress_saves_evidence_and_notes():
    request = MagicMock()
    request.url.path = "/people/perf/goals/test/progress"
    request.form = AsyncMock(
        return_value={
            "actual_value": "12",
            "notes": "Verified in CRM",
            "evidence": "Report 42",
        }
    )
    db, auth, kpi_id = MagicMock(), SimpleNamespace(organization_id=uuid4()), uuid4()
    with patch("app.services.people.perf.web.perf_web.PerformanceService") as factory:
        response = await PerfWebService().update_goal_progress_response(
            request, auth, db, str(kpi_id)
        )
    factory.return_value.update_kpi_progress.assert_called_once_with(
        auth.organization_id,
        kpi_id,
        actual_value=Decimal("12"),
        notes="Verified in CRM",
        evidence="Report 42",
    )
    assert "saved=1" in response.headers["location"]
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_failed_progress_does_not_report_saved():
    request = MagicMock()
    request.url.path = "/people/perf/goals/test/progress"
    request.form = AsyncMock(return_value={"actual_value": "12"})
    db, auth = MagicMock(), SimpleNamespace(organization_id=uuid4())
    with patch("app.services.people.perf.web.perf_web.PerformanceService") as factory:
        factory.return_value.update_kpi_progress.side_effect = ValueError("Not found")
        response = await PerfWebService().update_goal_progress_response(
            request, auth, db, str(uuid4())
        )
    assert (
        "error=" in response.headers["location"]
        and "saved=1" not in response.headers["location"]
    )
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
