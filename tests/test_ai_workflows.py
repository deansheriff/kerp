"""AI boundary tests use a real SQLAlchemy session, never a live provider."""

from datetime import date, timedelta
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.orm import Session

from app.models.domain_settings import (
    DomainSetting,
    DomainSettingHistory,
    SettingDomain,
    SettingScope,
    SettingValueType,
)
from app.models.finance.core_org.organization import Organization
from app.models.people.hr import Employee, EmployeeStatus
from app.models.people.hr.handbook import HRDocument, DocumentStatus
from app.models.people.perf.appraisal import Appraisal, AppraisalKRAScore
from app.models.people.perf.appraisal_cycle import AppraisalCycle
from app.models.people.perf.kpi import KPI
from app.models.people.recruit.job_opening import JobOpening
from app.models.support.category import TicketCategory
from app.models.support.comment import TicketComment, CommentType
from app.models.support.ticket import Ticket, TicketStatus
from app.services.coach.ai_workflows import (
    AIWorkflowService,
    AIForbidden,
    AINotFound,
    EvidenceDraft,
    HiringDraft,
    TicketDraft,
    validate_citations,
)
from app.services.coach.configuration import save_configuration
from app.services.coach.insight_engine import InsightEngine, LLMError


class Actor:
    def __init__(self, org_id, permissions=(), employee_id=None, admin=False):
        self.organization_id = org_id
        self.person_id = uuid4()
        self.employee_id = employee_id
        self.is_admin = admin
        self.permissions = set(permissions)

    def has_permission(self, permission):
        return self.is_admin or permission in self.permissions

    def has_module_access(self, module):
        return True


@pytest.fixture
def ai_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {
                s: None for s in ("hr", "perf", "recruit", "support", "core_org")
            }
        },
    )
    models = (
        Organization,
        DomainSetting,
        DomainSettingHistory,
        HRDocument,
        Employee,
        Appraisal,
        AppraisalKRAScore,
        AppraisalCycle,
        KPI,
        JobOpening,
        Ticket,
        TicketCategory,
        TicketComment,
    )
    for model in models:
        for column in model.__table__.columns:
            if type(column.type).__name__ == "PatchedJSONB":
                monkeypatch.setattr(column, "type", JSON())
            if column.server_default is not None and "gen_random_uuid" in str(
                column.server_default.arg
            ):
                monkeypatch.setattr(column, "server_default", None)
        model.__table__.create(engine)
    with Session(engine) as db:
        db.info["organization_id"] = uuid4()
        yield db
    engine.dispose()


@pytest.fixture
def llm():
    with (
        patch("app.services.coach.ai_workflows.InsightEngine") as factory,
        patch.object(AIWorkflowService, "_limit"),
    ):
        engine = factory.return_value
        engine._setting.return_value = "true"
        engine.last_model = "gemini/test-model"
        yield engine


def document(db, *, org_id=None, **kwargs):
    defaults = dict(
        document_id=uuid4(),
        organization_id=org_id or db.info["organization_id"],
        document_code=str(uuid4()),
        title="Annual leave policy",
        description="Annual leave is 20 days.",
        file_path="absent.pdf",
        file_name="policy.pdf",
        content_type="application/pdf",
        effective_date=date.today(),
        status=DocumentStatus.ACTIVE,
        applies_to_all_employees=True,
        created_by=uuid4(),
    )
    defaults.update(kwargs)
    row = HRDocument(**defaults)
    db.add(row)
    db.flush()
    return row


def test_tenant_session_required(ai_db):
    with pytest.raises(AIForbidden):
        AIWorkflowService(ai_db, Actor(uuid4(), admin=True))


@pytest.mark.parametrize(
    "workflow", ["hiring", "kpi", "appraisal", "knowledge", "support"]
)
def test_permission_denied_before_provider_or_query(ai_db, llm, workflow):
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"]))
    with pytest.raises(AIForbidden):
        service.generate(workflow, brief="test")
    llm.generate_structured.assert_not_called()


def test_knowledge_excludes_foreign_inactive_future_expired_and_department_docs(
    ai_db, llm
):
    org_id = ai_db.info["organization_id"]
    employee = Employee(
        employee_id=uuid4(),
        organization_id=org_id,
        person_id=uuid4(),
        employee_code="E1",
        department_id=uuid4(),
        date_of_joining=date.today(),
        status=EmployeeStatus.ACTIVE,
    )
    ai_db.add(employee)
    valid = document(ai_db)
    document(ai_db, org_id=uuid4())
    document(ai_db, status=DocumentStatus.DRAFT)
    document(ai_db, status=DocumentStatus.ARCHIVED)
    document(ai_db, effective_date=date.today() + timedelta(days=1))
    document(ai_db, expiry_date=date.today() - timedelta(days=1))
    denied = document(
        ai_db, applies_to_all_employees=False, applies_to_departments=[str(uuid4())]
    )
    service = AIWorkflowService(
        ai_db, Actor(org_id, ["selfservice:documents:read"], employee.employee_id)
    )
    with patch.object(service, "_document_text", wraps=service._document_text) as read:
        sources = service.knowledge_sources("annual leave")
        assert [s["id"] for s in sources] == [f"document:{valid.document_id}"]
        read.assert_called_once_with(valid)
    with pytest.raises(AINotFound):
        service.document_source(denied.document_id)


def test_no_sources_does_not_call_provider(ai_db, llm):
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"], admin=True))
    result = service.generate("knowledge", brief="leave")
    assert result["result"].gaps
    llm.generate_structured.assert_not_called()


def test_knowledge_citations_checked_against_scoped_sources(ai_db, llm):
    doc = document(ai_db)
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"], admin=True))
    llm.generate_structured.return_value = EvidenceDraft(
        statements=[
            dict(
                text="20 days",
                source_id=f"document:{doc.document_id}",
                quote="Annual leave is 20 days.",
            )
        ],
        gaps=[],
    )
    assert service.generate("knowledge", brief="annual leave")["result"].statements
    prompt = llm.generate_structured.call_args.kwargs["user_prompt"]
    assert "Annual leave is 20 days" in prompt
    llm.generate_structured.return_value = EvidenceDraft(
        statements=[
            dict(text="99 days", source_id=f"document:{uuid4()}", quote="Fake policy")
        ],
        gaps=[],
    )
    with pytest.raises(LLMError, match="unsupported citation"):
        service.generate("knowledge", brief="annual leave")
    llm.discard_cached_output.assert_called_once()


def test_file_path_cannot_escape_org(ai_db, tmp_path, monkeypatch):
    from app.services.people.hr.handbook_service import HRDocumentService

    monkeypatch.setattr(HRDocumentService, "UPLOAD_DIR", tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("CONFIDENTIAL OUTSIDE", encoding="utf-8")
    doc = document(ai_db, file_path=str(outside), content_type="text/plain")
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"], admin=True))
    assert "CONFIDENTIAL" not in service.document_source(doc.document_id)["text"]


def test_appraisal_requires_assigned_manager_not_just_review_permission(ai_db, llm):
    org_id = ai_db.info["organization_id"]
    row = Appraisal(
        organization_id=org_id,
        employee_id=uuid4(),
        manager_id=uuid4(),
        cycle_id=uuid4(),
    )
    ai_db.add(row)
    ai_db.flush()
    service = AIWorkflowService(
        ai_db,
        Actor(org_id, ["perf:appraisals:review", "perf:appraisals:read_team"], uuid4()),
    )
    with pytest.raises(AIForbidden):
        service.generate("appraisal", record_id=row.appraisal_id)
    llm.generate_structured.assert_not_called()


def test_foreign_ticket_is_not_visible(ai_db, llm):
    row = Ticket(organization_id=uuid4(), ticket_number="OTHER-1", subject="Secret")
    ai_db.add(row)
    ai_db.flush()
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"], admin=True))
    with pytest.raises(AINotFound):
        service.generate("support", record_id=row.ticket_id)
    llm.generate_structured.assert_not_called()


def test_appraisal_context_matches_employee_org_and_review_period(ai_db, llm):
    org_id = ai_db.info["organization_id"]
    employee_id, manager_id = uuid4(), uuid4()
    cycle = AppraisalCycle(
        organization_id=org_id,
        cycle_code="Q1",
        cycle_name="Q1",
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 3, 31),
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
    )
    ai_db.add(cycle)
    ai_db.flush()
    appraisal = Appraisal(
        organization_id=org_id,
        employee_id=employee_id,
        manager_id=manager_id,
        cycle_id=cycle.cycle_id,
        manager_overall_rating=3,
        final_rating=None,
    )
    ai_db.add(appraisal)
    for name, org, employee, start, end in [
        ("In period", org_id, employee_id, date(2026, 1, 1), date(2026, 3, 31)),
        ("Outside period", org_id, employee_id, date(2025, 1, 1), date(2025, 3, 31)),
        ("Other employee", org_id, uuid4(), date(2026, 1, 1), date(2026, 3, 31)),
        (
            "Foreign organization",
            uuid4(),
            employee_id,
            date(2026, 1, 1),
            date(2026, 3, 31),
        ),
    ]:
        ai_db.add(
            KPI(
                organization_id=org,
                employee_id=employee,
                kpi_name=name,
                period_start=start,
                period_end=end,
                target_value=50,
                actual_value=None,
                evidence="CRM report pending",
            )
        )
    ai_db.flush()
    llm.generate_structured.return_value = EvidenceDraft(
        statements=[], gaps=["Missing actuals"]
    )
    actor = Actor(
        org_id, ["perf:appraisals:review", "perf:appraisals:read_team"], manager_id
    )
    AIWorkflowService(ai_db, actor).generate(
        "appraisal", record_id=appraisal.appraisal_id
    )
    context = json.loads(llm.generate_structured.call_args.kwargs["user_prompt"])
    assert len(context["sources"]) == 1
    source = json.loads(context["sources"][0]["text"])
    assert source["name"] == "In period" and source["actual"] is None
    assert source["evidence"] == "CRM report pending"
    assert appraisal.manager_overall_rating == 3 and appraisal.final_rating is None
    assert not ai_db.dirty


def test_gemini_request_uses_configured_endpoint_bearer_key_and_schema():
    engine = InsightEngine()
    backend = SimpleNamespace(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key="test-secret",
        model_fast="test-model",
        model_standard="test-model",
        model_deep="test-model",
        is_configured=lambda: True,
    )
    engine._backends = {"gemini": backend}
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "choices": [
            {"message": {"content": '{"statements": [], "gaps": ["No evidence"]}'}}
        ],
        "usage": {"total_tokens": 42},
    }
    with (
        patch.object(engine, "_backend_order", return_value=["gemini"]),
        patch(
            "app.services.coach.insight_engine.cache_service",
            SimpleNamespace(is_available=False),
        ),
        patch("httpx.Client") as client,
    ):
        client.return_value.__enter__.return_value.post.return_value = response
        result = engine.generate_structured(
            tier="standard",
            system_prompt="Draft only",
            user_prompt="question",
            output_model=EvidenceDraft,
        )
    call = client.return_value.__enter__.return_value.post.call_args
    assert call.args == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    )
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-secret"
    assert "Output JSON schema" in call.kwargs["json"]["messages"][0]["content"]
    assert result.gaps == ["No evidence"] and engine.tokens_used == 42


def test_support_suggestions_never_mutate_ticket(ai_db, llm):
    org_id = ai_db.info["organization_id"]
    ticket = Ticket(
        organization_id=org_id,
        ticket_number="T-1",
        subject="Cannot login",
        description="Login failed",
        contact_email="private@example.com",
    )
    ai_db.add(ticket)
    ai_db.add(
        TicketCategory(
            organization_id=org_id,
            category_code="LOGIN",
            category_name="Login",
            is_active=True,
        )
    )
    ai_db.flush()
    ai_db.add_all(
        [
            TicketComment(
                ticket_id=ticket.ticket_id,
                content="Public follow-up",
                comment_type=CommentType.COMMENT,
            ),
            TicketComment(
                ticket_id=ticket.ticket_id,
                content="INTERNAL SECRET",
                is_internal=True,
                comment_type=CommentType.INTERNAL_NOTE,
            ),
        ]
    )
    ai_db.flush()
    llm.generate_structured.return_value = TicketDraft(
        category_code="LOGIN",
        priority="HIGH",
        rationale="Access issue",
        suggested_reply="What error appears?",
        missing_information=[],
    )
    service = AIWorkflowService(
        ai_db, Actor(org_id, ["support:tickets:read", "support:tickets:update"])
    )
    result = service.generate("support", record_id=ticket.ticket_id)
    assert result["result"].category_code == "LOGIN"
    assert ticket.category_id is None and ticket.status == TicketStatus.OPEN
    assert (
        "private@example.com"
        not in llm.generate_structured.call_args.kwargs["user_prompt"]
    )
    assert (
        "INTERNAL SECRET" not in llm.generate_structured.call_args.kwargs["user_prompt"]
    )
    assert "Public follow-up" in llm.generate_structured.call_args.kwargs["user_prompt"]
    llm.generate_structured.return_value.category_code = "FOREIGN"
    with pytest.raises(LLMError, match="unknown category"):
        service.generate("support", record_id=ticket.ticket_id)
    llm.discard_cached_output.assert_called_once()


def test_rejected_structured_output_can_be_evicted_for_retry():
    engine = InsightEngine(organization_id=uuid4())
    engine._last_cache_key = "test:response"
    with patch("app.services.coach.insight_engine.cache_service") as cache:
        cache.is_available = True
        engine.discard_cached_output()
    cache.delete.assert_called_once_with("test:response")


def test_schema_rejects_automated_ratings_and_invalid_kpi_weights():
    with pytest.raises(ValidationError):
        EvidenceDraft.model_validate(dict(statements=[], gaps=[], final_rating=5))
    with pytest.raises(ValidationError):
        HiringDraft.model_validate(
            dict(
                description="Job",
                requirements=[],
                interview_questions=[],
                assumptions=[],
                kpis=[
                    dict(
                        name="Leads",
                        kra="Growth",
                        target=30,
                        unit="leads",
                        weight_percent=30,
                        measurement="In 90 days",
                        evidence_required="CRM",
                    )
                ],
            )
        )
    with pytest.raises(LLMError):
        validate_citations(
            EvidenceDraft(
                statements=[dict(text="Claim", source_id="a", quote="fake")], gaps=[]
            ),
            [{"id": "a", "text": "real"}],
        )


def test_configuration_is_org_specific_atomic_and_keeps_blank_secret(ai_db):
    org_id = ai_db.info["organization_id"]
    global_key = DomainSetting(
        domain=SettingDomain.coach,
        key="gemini_api_key",
        value_text="global-secret",
        value_type=SettingValueType.string,
        scope=SettingScope.GLOBAL,
        is_secret=True,
    )
    ai_db.add(global_key)
    ai_db.flush()
    assert save_configuration(
        ai_db, org_id, {"gemini_api_key": "org-secret", "ai_enabled": "true"}
    ) == (True, None)
    assert global_key.value_text == "global-secret"
    assert save_configuration(ai_db, org_id, {"gemini_api_key": ""}) == (True, None)
    row = ai_db.scalar(
        select(DomainSetting).where(
            DomainSetting.organization_id == org_id,
            DomainSetting.key == "gemini_api_key",
        )
    )
    assert row.value_text == "org-secret" and row.is_secret
    success, _ = save_configuration(
        ai_db,
        org_id,
        {"gemini_api_key": "replaced", "gemini_base_url": "http://bad.test"},
    )
    assert not success and row.value_text == "org-secret"


def test_gemini_routing_and_cache_isolation():
    with patch.object(
        InsightEngine,
        "_setting",
        side_effect=lambda key, fallback: {
            "backends": "gemini",
            "default_backend": "gemini",
        }.get(key, ""),
    ):
        a = InsightEngine(organization_id=uuid4())
        b = InsightEngine(organization_id=uuid4())
        assert a._backend_order("deepseek") == ["gemini"]
        args = dict(
            backend="gemini",
            model="example",
            tier="standard",
            system_prompt="System",
            user_prompt="User",
        )
        assert a._cache_key(**args) != b._cache_key(**args)


def test_provider_settings_respect_org_and_explicit_false_zero(ai_db):
    org_id = ai_db.info["organization_id"]
    save_configuration(
        ai_db,
        org_id,
        {"ai_enabled": "false", "max_retries": "0", "gemini_api_key": "own-secret"},
    )
    ai_db.add(
        DomainSetting(
            organization_id=uuid4(),
            scope=SettingScope.ORG_SPECIFIC,
            domain=SettingDomain.coach,
            key="gemini_api_key",
            value_type=SettingValueType.string,
            value_text="foreign-secret",
            is_secret=True,
        )
    )
    ai_db.flush()
    engine = InsightEngine(ai_db)
    assert engine.organization_id == org_id
    assert engine._setting("ai_enabled", "coach_ai_enabled").lower() == "false"
    assert engine._max_retries == 0
    assert engine._backends["gemini"].api_key == "own-secret"
    with pytest.raises(LLMError, match="tenant-scoped"):
        InsightEngine(ai_db, organization_id=uuid4())
    ai_db.info["allow_cross_org"] = True
    with pytest.raises(LLMError, match="tenant-scoped"):
        InsightEngine(ai_db, organization_id=org_id)


def test_disabled_and_redis_unavailable_do_not_call_provider(ai_db):
    service = AIWorkflowService(ai_db, Actor(ai_db.info["organization_id"], admin=True))
    with patch("app.services.coach.ai_workflows.InsightEngine") as factory:
        factory.return_value._setting.return_value = "false"
        with pytest.raises(LLMError, match="disabled"):
            service.generate("hiring", brief="Digital marketer, Abuja")
        factory.return_value.generate_structured.assert_not_called()
    with patch(
        "app.services.coach.ai_workflows.cache_service", SimpleNamespace(client=None)
    ):
        with pytest.raises(LLMError, match="Redis"):
            service._limit()


def test_no_company_data_is_placed_in_provider_failure_logs():
    engine = InsightEngine()
    backend = SimpleNamespace(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key="secret",
    )
    response = MagicMock(status_code=400, text="private provider error")
    with patch("httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        with pytest.raises(LLMError, match="^LLM HTTP 400$"):
            engine._call_chat_completions(
                backend=backend,
                model="test",
                system_prompt="system",
                user_prompt="private",
                temperature=0.2,
            )
