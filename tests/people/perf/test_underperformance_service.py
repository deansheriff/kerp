"""
Tests for UnderperformanceService — business logic validation.

Uses SimpleNamespace/MagicMock to test threshold comparisons and scoring
logic without hitting the database.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.people.perf.underperformance_service import (
    UnderperformanceService,
    UnderperformanceServiceError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service() -> UnderperformanceService:
    db = MagicMock()
    return UnderperformanceService(db)


def make_kra_score(raw_score_percentage: float | None) -> SimpleNamespace:
    return SimpleNamespace(
        score_id=uuid.uuid4(),
        raw_score_percentage=Decimal(str(raw_score_percentage))
        if raw_score_percentage is not None
        else None,
    )


def make_appraisal(
    employee_id: uuid.UUID | None = None,
    appraisal_id: uuid.UUID | None = None,
    final_score: float | None = None,
    is_quarterly: bool = False,
    kra_scores: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        appraisal_id=appraisal_id or uuid.uuid4(),
        employee_id=employee_id or uuid.uuid4(),
        organization_id=uuid.uuid4(),
        is_quarterly=is_quarterly,
        final_score=Decimal(str(final_score)) if final_score is not None else None,
        kra_scores=kra_scores or [],
    )


def make_employee(
    employee_id: uuid.UUID | None = None,
    date_of_joining: date | None = None,
    confirmation_date: date | None = None,
    status: str = "ACTIVE",
) -> SimpleNamespace:
    return SimpleNamespace(
        employee_id=employee_id or uuid.uuid4(),
        organization_id=uuid.uuid4(),
        date_of_joining=date_of_joining or date(2024, 1, 1),
        confirmation_date=confirmation_date,
        status=status,
    )


# ---------------------------------------------------------------------------
# Error class hierarchy
# ---------------------------------------------------------------------------


class TestErrorHierarchy:
    def test_underperformance_service_error_is_exception(self) -> None:
        err = UnderperformanceServiceError("test")
        assert isinstance(err, Exception)

    def test_underperformance_service_error_message(self) -> None:
        err = UnderperformanceServiceError("something went wrong")
        assert "something went wrong" in str(err)


# ---------------------------------------------------------------------------
# Annual trigger logic
# ---------------------------------------------------------------------------


class TestAnnualTriggerLogic:
    """Test the 50% Fair KPIs threshold for annual appraisals."""

    def test_flags_employee_with_exactly_50pct_fair_kpis(self) -> None:
        """Employee with exactly 50% KPIs below 70 is flagged."""
        svc = make_service()
        emp_id = uuid.uuid4()
        appraisal = make_appraisal(
            employee_id=emp_id,
            is_quarterly=False,
            kra_scores=[
                make_kra_score(65.0),   # fair (< 70)
                make_kra_score(60.0),   # fair (< 70)
                make_kra_score(80.0),   # good
                make_kra_score(85.0),   # good
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)

        assert result is not None
        assert result["employee_id"] == emp_id
        assert result["fair_count"] == 2
        assert result["total_kpis"] == 4
        assert result["percentage"] == pytest.approx(50.0)

    def test_flags_employee_with_more_than_50pct_fair_kpis(self) -> None:
        """Employee with >50% KPIs below 70 is flagged."""
        svc = make_service()
        emp_id = uuid.uuid4()
        appraisal = make_appraisal(
            employee_id=emp_id,
            is_quarterly=False,
            kra_scores=[
                make_kra_score(50.0),   # fair
                make_kra_score(60.0),   # fair
                make_kra_score(69.9),   # fair (just below threshold)
                make_kra_score(90.0),   # good
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)

        assert result is not None
        assert result["fair_count"] == 3
        assert result["total_kpis"] == 4
        assert result["percentage"] == pytest.approx(75.0)

    def test_skips_employee_with_all_good_kpis(self) -> None:
        """Employee with all KPIs >= 70 is not flagged."""
        svc = make_service()
        appraisal = make_appraisal(
            is_quarterly=False,
            kra_scores=[
                make_kra_score(70.0),   # exactly at threshold — good
                make_kra_score(80.0),
                make_kra_score(90.0),
                make_kra_score(100.0),
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)

        assert result is None

    def test_skips_employee_below_50pct_fair(self) -> None:
        """Employee with <50% KPIs below 70 is not flagged (only 1 of 4 = 25%)."""
        svc = make_service()
        appraisal = make_appraisal(
            is_quarterly=False,
            kra_scores=[
                make_kra_score(60.0),   # fair
                make_kra_score(75.0),
                make_kra_score(80.0),
                make_kra_score(85.0),
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)

        assert result is None

    def test_skips_kra_scores_without_raw_score_percentage(self) -> None:
        """KRA scores with None raw_score_percentage are excluded from count."""
        svc = make_service()
        appraisal = make_appraisal(
            is_quarterly=False,
            kra_scores=[
                make_kra_score(60.0),   # fair
                make_kra_score(None),   # not scored — excluded
                make_kra_score(None),   # not scored — excluded
                make_kra_score(80.0),   # good
            ],
        )

        # Only 2 scored KPIs: 1 fair / 2 total = 50% → flagged
        result = svc._evaluate_annual_trigger(appraisal)
        assert result is not None
        assert result["total_kpis"] == 2
        assert result["fair_count"] == 1

    def test_returns_none_when_no_scored_kpis(self) -> None:
        """Appraisal with no scored KPIs produces no result (can't evaluate)."""
        svc = make_service()
        appraisal = make_appraisal(
            is_quarterly=False,
            kra_scores=[
                make_kra_score(None),
                make_kra_score(None),
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)
        assert result is None

    def test_includes_appraisal_id_in_result(self) -> None:
        """Result includes the appraisal_id for traceability."""
        svc = make_service()
        appraisal_id = uuid.uuid4()
        appraisal = make_appraisal(
            appraisal_id=appraisal_id,
            is_quarterly=False,
            kra_scores=[
                make_kra_score(60.0),
                make_kra_score(55.0),
            ],
        )

        result = svc._evaluate_annual_trigger(appraisal)
        assert result is not None
        assert result["appraisal_id"] == appraisal_id


# ---------------------------------------------------------------------------
# Quarterly trigger logic
# ---------------------------------------------------------------------------


class TestQuarterlyTriggerLogic:
    """Test the 3-quarters-below-70 threshold."""

    def test_flags_employee_with_3_quarters_below_70(self) -> None:
        """Employee with exactly 3 quarters below 70 is flagged."""
        svc = make_service()
        quarterly_scores = [65.0, 60.0, 68.0]  # all below 70

        result = svc._evaluate_quarterly_trigger(
            employee_id=uuid.uuid4(),
            quarterly_scores=quarterly_scores,
        )

        assert result is not None
        assert result["quarters_below"] == 3

    def test_flags_employee_with_more_than_3_quarters_below_70(self) -> None:
        """Employee with 4 quarters below 70 is still flagged."""
        svc = make_service()
        quarterly_scores = [60.0, 65.0, 55.0, 68.0]  # all below 70

        result = svc._evaluate_quarterly_trigger(
            employee_id=uuid.uuid4(),
            quarterly_scores=quarterly_scores,
        )

        assert result is not None
        assert result["quarters_below"] == 4

    def test_skips_employee_with_only_2_quarters_below_70(self) -> None:
        """Employee with 2 quarters below 70 is not yet flagged."""
        svc = make_service()
        quarterly_scores = [60.0, 65.0, 75.0]

        result = svc._evaluate_quarterly_trigger(
            employee_id=uuid.uuid4(),
            quarterly_scores=quarterly_scores,
        )

        assert result is None

    def test_skips_employee_with_no_quarters_below_70(self) -> None:
        """Employee with all quarterly scores >= 70 is not flagged."""
        svc = make_service()
        quarterly_scores = [70.0, 80.0, 85.0, 90.0]

        result = svc._evaluate_quarterly_trigger(
            employee_id=uuid.uuid4(),
            quarterly_scores=quarterly_scores,
        )

        assert result is None

    def test_result_includes_quarterly_scores(self) -> None:
        """Result includes the quarterly_scores list for context."""
        svc = make_service()
        emp_id = uuid.uuid4()
        scores = [60.0, 65.0, 55.0]

        result = svc._evaluate_quarterly_trigger(
            employee_id=emp_id,
            quarterly_scores=scores,
        )

        assert result is not None
        assert result["employee_id"] == emp_id
        assert result["quarterly_scores"] == scores

    def test_exactly_70_is_not_below_threshold(self) -> None:
        """Score of exactly 70.0 is NOT counted as below threshold."""
        svc = make_service()
        quarterly_scores = [70.0, 70.0, 70.0]

        result = svc._evaluate_quarterly_trigger(
            employee_id=uuid.uuid4(),
            quarterly_scores=quarterly_scores,
        )

        assert result is None


# ---------------------------------------------------------------------------
# Probation milestone logic
# ---------------------------------------------------------------------------


class TestProbationLogic:
    """Test the 21-month probation milestone detection."""

    def test_calculates_months_correctly_for_21_months(self) -> None:
        """Employee joining 21 months ago should be flagged."""
        svc = make_service()
        today = date.today()
        # Join date 21 months ago (approximate via days)
        join_date = date(today.year - 2, today.month, today.day) + timedelta(days=30 * 3)
        # More precise: subtract exactly 21 months
        year = today.year
        month = today.month - 21
        while month <= 0:
            month += 12
            year -= 1
        join_date = date(year, month, today.day)

        result = svc._evaluate_probation_milestone(
            employee=make_employee(
                date_of_joining=join_date,
                confirmation_date=None,
            )
        )

        assert result is not None

    def test_flags_employee_approaching_21_months(self) -> None:
        """Employee whose 21-month date is within 30 days is flagged."""
        svc = make_service()
        # 21 months from now minus 15 days means milestone is 15 days away
        today = date.today()
        days_until_milestone = 15

        # Calculate join date: milestone is today + days_until_milestone,
        # milestone = join + 21 months ≈ join + 638 days
        milestone_date = today + timedelta(days=days_until_milestone)
        approx_21_months_days = 21 * 30
        join_date = milestone_date - timedelta(days=approx_21_months_days)

        result = svc._evaluate_probation_milestone(
            employee=make_employee(
                date_of_joining=join_date,
                confirmation_date=None,
            )
        )

        assert result is not None
        assert "milestone_date" in result
        assert "months_of_service" in result

    def test_skips_already_confirmed_employee(self) -> None:
        """Employee already confirmed (confirmation_date set) is skipped."""
        svc = make_service()
        today = date.today()
        year = today.year
        month = today.month - 21
        while month <= 0:
            month += 12
            year -= 1
        join_date = date(year, month, today.day)

        result = svc._evaluate_probation_milestone(
            employee=make_employee(
                date_of_joining=join_date,
                confirmation_date=date(2025, 6, 1),  # already confirmed
            )
        )

        assert result is None

    def test_skips_employee_with_milestone_more_than_30_days_away(self) -> None:
        """Employee whose 21-month milestone is > 30 days away is not flagged."""
        svc = make_service()
        today = date.today()
        # Join date is only 10 months ago — milestone is 11 months away
        join_date = today - timedelta(days=10 * 30)

        result = svc._evaluate_probation_milestone(
            employee=make_employee(
                date_of_joining=join_date,
                confirmation_date=None,
            )
        )

        assert result is None

    def test_skips_employee_past_21_month_milestone_by_more_than_30_days(self) -> None:
        """Employee who passed the 21-month milestone long ago is not flagged again."""
        svc = make_service()
        # Join date 2 years ago — milestone was 3 months ago
        join_date = date.today() - timedelta(days=365 * 2 + 90)

        result = svc._evaluate_probation_milestone(
            employee=make_employee(
                date_of_joining=join_date,
                confirmation_date=None,
            )
        )

        assert result is None

    def test_result_includes_required_fields(self) -> None:
        """Result dict includes employee_id, date_of_joining, months_of_service, milestone_date."""
        svc = make_service()
        emp_id = uuid.uuid4()
        today = date.today()
        year = today.year
        month = today.month - 21
        while month <= 0:
            month += 12
            year -= 1
        join_date = date(year, month, today.day)

        emp = make_employee(
            employee_id=emp_id,
            date_of_joining=join_date,
            confirmation_date=None,
        )
        result = svc._evaluate_probation_milestone(employee=emp)

        assert result is not None
        assert result["employee_id"] == emp_id
        assert result["date_of_joining"] == join_date
        assert "months_of_service" in result
        assert "milestone_date" in result
