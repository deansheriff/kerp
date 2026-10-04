from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.coach.insight_engine import InsightEngine, LLMError
from app.services.coach.narration import (
    Narration,
    narrate_daily_insights,
    narrate_report,
)


def engine_mock(enabled=True):
    engine = MagicMock()
    engine._setting.return_value = "true" if enabled else "false"
    engine.generate_structured.return_value = Narration(
        explanation="Investigate overdue items.", limitations="Aggregate data only."
    )
    engine.last_model = "gemini/test"
    engine.tokens_used = 123
    return engine


def test_daily_narration_preserves_facts_and_omits_identifying_evidence():
    db = MagicMock()
    row = SimpleNamespace(
        title="Overdue receivables",
        category="CASH_FLOW",
        severity="WARNING",
        evidence={
            "count": 3,
            "amount": "12.50",
            "name": "Confidential client",
            "customers": [{"email": "private@example.com"}],
        },
        detail=None,
        summary="Original facts",
        coaching_action="Original action",
    )
    db.scalars.return_value.all.return_value = [row]
    engine = engine_mock()
    with patch("app.services.coach.narration.InsightEngine", return_value=engine):
        narrate_daily_insights(db, uuid4())
    assert row.detail.startswith("AI explanation")
    assert (
        row.summary == "Original facts"
        and row.severity == "WARNING"
        and row.coaching_action == "Original action"
    )
    prompt = engine.generate_structured.call_args.kwargs["user_prompt"]
    assert (
        "12.50" in prompt and "Confidential" not in prompt and "private@" not in prompt
    )


def test_provider_outage_keeps_daily_facts_and_stops_batch():
    db = MagicMock()
    row = SimpleNamespace(
        title="Signal",
        category="CASH_FLOW",
        severity="WARNING",
        evidence={},
        detail=None,
    )
    db.scalars.return_value.all.return_value = [row, row]
    engine = engine_mock()
    engine.generate_structured.side_effect = LLMError("Unavailable")
    with patch("app.services.coach.narration.InsightEngine", return_value=engine):
        narrate_daily_insights(db, uuid4())
    assert row.detail is None
    engine.generate_structured.assert_called_once()


@pytest.mark.parametrize("enabled", [True, False])
def test_report_narration_is_optional_and_keeps_original_summary(enabled):
    report = SimpleNamespace(
        organization_id=uuid4(),
        audience="HR",
        period_start="2026-01-01",
        period_end="2026-01-07",
        key_metrics=[
            {"metric": "Count", "value": 5},
            {"metric": "People", "value": [{"name": "PRIVATE"}]},
        ],
        executive_summary="Original summary",
        model_used=None,
        tokens_used=0,
    )
    engine = engine_mock(enabled)
    with patch("app.services.coach.narration.InsightEngine", return_value=engine):
        narrate_report(MagicMock(), report)
    assert report.executive_summary.startswith("Original summary")
    if enabled:
        assert "AI explanation" in report.executive_summary
        assert report.model_used == "gemini/test" and report.tokens_used == 123
        assert (
            "PRIVATE" not in engine.generate_structured.call_args.kwargs["user_prompt"]
        )
    else:
        assert report.executive_summary == "Original summary"
        engine.generate_structured.assert_not_called()


def test_budget_rejection_prevents_external_call():
    engine = InsightEngine(organization_id=uuid4())
    client = MagicMock()
    client.pipeline.return_value.__enter__.return_value.execute.return_value = [
        9999999999,
        True,
    ]
    with patch(
        "app.services.coach.insight_engine.cache_service",
        SimpleNamespace(client=client),
    ):
        with pytest.raises(LLMError, match="budget reached"):
            engine._reserve_budget("system", "user")
    client.decrby.assert_called_once()


def test_budget_storage_failure_is_closed():
    engine = InsightEngine(organization_id=uuid4())
    with patch(
        "app.services.coach.insight_engine.cache_service", SimpleNamespace(client=None)
    ):
        with pytest.raises(LLMError, match="storage is unavailable"):
            engine._reserve_budget("system", "user")


@pytest.mark.parametrize(
    "name,module,cls",
    [
        ("generate_daily_data_quality_insights", "data_quality", "DataQualityAnalyzer"),
        ("generate_daily_banking_health_insights", "banking", "BankingHealthAnalyzer"),
        (
            "generate_daily_expense_approval_insights",
            "expense",
            "ExpenseApprovalAnalyzer",
        ),
        ("generate_daily_ar_overdue_insights", "ar_overdue", "AROverdueAnalyzer"),
        ("generate_daily_ap_due_insights", "ap_due", "APDueAnalyzer"),
        ("generate_daily_cash_flow_insights", "cash_flow", "CashFlowAnalyzer"),
        ("generate_daily_compliance_insights", "compliance", "ComplianceAnalyzer"),
        ("generate_daily_workforce_insights", "workforce", "WorkforceAnalyzer"),
        ("generate_daily_supply_chain_insights", "supply_chain", "SupplyChainAnalyzer"),
        ("generate_daily_revenue_insights", "revenue", "RevenueAnalyzer"),
        ("generate_daily_efficiency_insights", "efficiency", "EfficiencyAnalyzer"),
    ],
)
def test_each_daily_task_invokes_narration(name, module, cls):
    from app.tasks import coach

    org_id = uuid4()
    db = MagicMock()
    cross = MagicMock()
    cross.scalars.return_value.all.return_value = [org_id]
    with (
        patch.object(coach.app_settings, "coach_enabled", True, create=True),
        patch.object(coach.app_settings, "coach_max_insights_per_run", 20, create=True),
        patch.object(coach, "cross_org_session") as cross_session,
        patch.object(coach, "session_for_org") as scoped_session,
        patch(f"app.services.coach.analyzers.{module}.{cls}") as analyzer,
        patch.object(coach, "narrate_daily_insights") as narrate,
    ):
        cross_session.return_value.__enter__.return_value = cross
        scoped_session.return_value.__enter__.return_value = db
        analyzer.return_value.upsert_daily_org_insights.return_value = 1
        analyzer.return_value.upsert_daily_insights.return_value = 1
        result = getattr(coach, name).run(str(org_id))
    assert not result["errors"]
    narrate.assert_called_once_with(db, org_id)
    db.commit.assert_called_once()


@pytest.mark.parametrize("audience", ["finance", "hr"])
def test_each_weekly_task_invokes_narration(audience):
    from app.tasks import coach

    org_id = uuid4()
    db, cross, report = MagicMock(), MagicMock(), MagicMock()
    cross.scalars.return_value.all.return_value = [org_id]
    name = f"generate_weekly_{audience}_report"
    with (
        patch.object(coach.app_settings, "coach_enabled", True, create=True),
        patch.object(coach, "cross_org_session") as cross_session,
        patch.object(coach, "session_for_org") as scoped_session,
        patch("app.services.coach.report_generator.ReportGenerator") as generator,
        patch.object(coach, "narrate_report") as narrate,
    ):
        cross_session.return_value.__enter__.return_value = cross
        scoped_session.return_value.__enter__.return_value = db
        getattr(generator.return_value, name).return_value = report
        result = getattr(coach, name).run(str(org_id))
    assert result["reports_written"] == 1 and not result["errors"]
    narrate.assert_called_once_with(db, report)
    db.commit.assert_called_once()
