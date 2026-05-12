from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from starlette.datastructures import QueryParams
from starlette.requests import Request

from app.templates import templates
from app.services.common import PaginatedResult
from app.services.people.recruit.web import report_web
from app.services.people.recruit.web.report_web import ReportWebService


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_job_applicant_report_export_uses_selected_dynamic_fields(monkeypatch):
    org_id = uuid4()
    job_id = uuid4()
    applicant_id = uuid4()
    applicant = SimpleNamespace(
        applicant_id=applicant_id,
        application_number="APP-001",
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone=None,
        applied_on=date(2026, 5, 12),
        status=SimpleNamespace(value="NEW"),
        source="Website",
    )
    skill_field = SimpleNamespace(
        field_key="primary_skill",
        label="Primary Skill",
        field_type=SimpleNamespace(value="TEXT"),
        is_filterable=True,
    )

    class FakeRecruitmentService:
        def __init__(self, db):
            self.db = db

        def get_job_opening(self, org, opening_id):
            return SimpleNamespace(
                job_opening_id=job_id,
                job_code="ENG-1",
                application_form_version_id=uuid4(),
            )

        def list_job_applicant_form_fields(self, org, opening_id):
            return [skill_field]

        def list_job_applicant_report_fields(self, org, opening_id):
            return [skill_field]

        def list_job_applicant_report(self, *args, **kwargs):
            assert kwargs["pagination"] is None
            return PaginatedResult(items=[applicant], total=1)

    class FakeFormEngineService:
        def __init__(self, db):
            self.db = db

        def list_subject_answer_values(self, org, subject_type, subject_ids):
            assert subject_type == "JOB_APPLICANT"
            assert subject_ids == [applicant_id]
            return {applicant_id: {"primary_skill": "Python"}}

    monkeypatch.setattr(report_web, "RecruitmentService", FakeRecruitmentService)
    monkeypatch.setattr(report_web, "FormEngineService", FakeFormEngineService)

    response = ReportWebService().export_job_applicant_report_csv_response(
        _request("/people/recruit/jobs/job/report/export"),
        SimpleNamespace(organization_id=org_id),
        SimpleNamespace(),
        str(job_id),
        fields=["system:applicant_name", "field:primary_skill"],
    )

    assert response.media_type == "text/csv; charset=utf-8"
    assert "job_applicants_ENG-1_" in response.headers["Content-Disposition"]
    assert response.body.decode().splitlines()[:2] == [
        "Applicant Name,Primary Skill",
        "Ada Lovelace,Python",
    ]


def test_job_applicant_report_export_escapes_spreadsheet_formulas():
    assert ReportWebService._csv_safe_cell("=cmd|calc") == "'=cmd|calc"
    assert ReportWebService._csv_safe_cell("+SUM(A1:A2)") == "'+SUM(A1:A2)"
    assert ReportWebService._csv_safe_cell("plain text") == "plain text"


def test_job_applicant_report_template_renders_export_panel():
    html = templates.env.get_template(
        "people/recruit/reports/job_applicants.html"
    ).render(
        request=SimpleNamespace(state=SimpleNamespace()),
        user={},
        current_user={},
        organization={},
        csrf_token="token",
        active_module="recruit",
        opening=SimpleNamespace(
            job_opening_id=uuid4(),
            job_title="Software Engineer",
            job_code="ENG-1",
            department=SimpleNamespace(department_name="Engineering"),
        ),
        pipeline=SimpleNamespace(
            total=0,
            new=0,
            screening=0,
            shortlisted=0,
            selected=0,
            hired=0,
        ),
        active_filters=[],
        search="",
        status="",
        source="",
        statuses=["NEW"],
        sort="applied_on",
        direction="desc",
        dynamic_columns=[],
        filterable_fields=[],
        export_system_fields=ReportWebService.JOB_APPLICANT_EXPORT_FIELDS,
        export_fields=[
            SimpleNamespace(field_key="primary_skill", label="Primary Skill")
        ],
        request_params=QueryParams(""),
        applicants=[],
        dynamic_values={},
        page=1,
        total_pages=1,
        total_count=0,
        total=0,
        limit=20,
        has_prev=False,
        has_next=False,
        pagination_filters={},
    )

    assert "Applicant Report" in html
    assert "Export CSV" in html
    assert "field:primary_skill" in html
