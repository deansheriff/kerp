from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.models.domain_settings import (
    DomainSetting,
    SettingDomain,
    SettingScope,
    SettingValueType,
)
from app.models.finance.core_org.organization import Organization, PerformanceMode
from app.models.people.hr import (
    Department,
    Designation,
    Employee,
    EmployeeStatus,
    Position,
    PositionAssignment,
    PositionAssignmentType,
)
from app.models.people.perf.appraisal_template import (
    AppraisalTemplate,
    AppraisalTemplateKRA,
)
from app.models.people.perf.kpi import KPI, KPIStatus
from app.models.people.perf.kra import KRA
from app.models.people.recruit.job_opening import JobOpening, JobOpeningStatus
from app.models.people.recruit.job_applicant import JobApplicant
from app.models.person import Person
from app.db.org_listener import _add_org_filter
from app.services.people.recruit.recruit_service import RecruitmentService
from scripts.seed_sherpackage_digital_marketer import (
    JOB_CODE,
    JOB_TEXT,
    POSITION_CODE,
    TARGETS,
    seed_job_package,
)
from scripts.seed_sherpackage_digital_marketer_on_start import SEED_KEY, seed_once

TABLE_MODELS = (
    Organization,
    DomainSetting,
    Person,
    Department,
    Designation,
    Employee,
    Position,
    PositionAssignment,
    KRA,
    AppraisalTemplate,
    AppraisalTemplateKRA,
    KPI,
    JobOpening,
    JobApplicant,
)


@pytest.fixture
def marketing_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {
                s: None for s in ("core_org", "hr", "perf", "recruit", "audit")
            },
        },
    )
    for model in TABLE_MODELS:
        for column in model.__table__.columns:
            if column.server_default is not None and "gen_random_uuid" in str(
                column.server_default.arg
            ):
                monkeypatch.setattr(column, "server_default", None)
        model.__table__.create(engine)
    with Session(engine, autoflush=False) as db:
        org_id = uuid4()
        db.info["organization_id"] = org_id
        db.add(
            Organization(
                organization_id=org_id,
                organization_code="SHP",
                slug="sherpackage",
                legal_name="Sherpackage",
                functional_currency_code="NGN",
                presentation_currency_code="NGN",
                fiscal_year_end_month=12,
                fiscal_year_end_day=31,
                performance_mode=PerformanceMode.PRIVATE,
            )
        )
        db.flush()
        db.add(
            Position(
                organization_id=org_id,
                position_code="SHP-CEO",
                position_name="Chief Executive Officer",
                is_active=True,
                is_vacant=True,
            )
        )
        db.flush()
        yield db, org_id
    engine.dispose()


def rows(db, model, org_id):
    return list(db.scalars(select(model).where(model.organization_id == org_id)))


def test_creates_abuja_vacancy_and_weighted_template_without_fake_employee(
    marketing_db,
):
    db, org_id = marketing_db
    job, counts = seed_job_package(db, org_id)
    assert job.job_code == JOB_CODE
    assert job.job_title == "Digital Marketer"
    assert job.employment_type == "FULL_TIME"
    assert job.location == "Abuja, Nigeria"
    assert job.is_remote is False
    assert job.status == JobOpeningStatus.DRAFT
    assert job.min_salary is None and job.max_salary is None
    assert job.closes_on is None and job.posted_on is None
    assert job.description == JOB_TEXT.read_text(encoding="utf-8").strip()
    assert job.position.is_vacant is True
    assert job.position.designation_id == job.designation_id
    assert job.position.department_id == job.department_id
    assert job.position.parent_position.position_code == "SHP-CEO"
    assert counts["job_opening"] == 1
    assert len(rows(db, KRA, org_id)) == 6
    template = rows(db, AppraisalTemplate, org_id)[0]
    assert len(template.kras) == 6
    assert sum(k.weightage for k in template.kras) == Decimal("100")
    assert template.designation_id == job.designation_id
    assert rows(db, Employee, org_id) == []
    assert rows(db, KPI, org_id) == []


def test_rerun_preserves_edits_and_does_not_republish_closed_job(marketing_db):
    db, org_id = marketing_db
    job, _ = seed_job_package(db, org_id, publish=True)
    job.description = "Edited by HR"
    job.status = JobOpeningStatus.CLOSED
    job.location = "Abuja - agreed office location"
    template = rows(db, AppraisalTemplate, org_id)[0]
    template.description = "HR review instructions"
    db.flush()
    again, counts = seed_job_package(db, org_id, publish=True)
    assert again.job_opening_id == job.job_opening_id
    assert counts == {}
    assert job.description == "Edited by HR"
    assert job.status == JobOpeningStatus.CLOSED
    assert job.location == "Abuja - agreed office location"
    assert template.description == "HR review instructions"


def test_publish_is_explicit_and_idempotent(marketing_db):
    db, org_id = marketing_db
    job, _ = seed_job_package(db, org_id)
    assert job.status == JobOpeningStatus.DRAFT
    job, counts = seed_job_package(db, org_id, publish=True)
    assert job.status == JobOpeningStatus.OPEN
    assert job.posted_on is not None
    assert counts == {"job_published": 1}
    original_date = job.posted_on
    _, counts = seed_job_package(db, org_id, publish=True)
    assert counts == {}
    assert job.posted_on == original_date


def test_dry_run_transaction_leaves_no_records(marketing_db):
    db, org_id = marketing_db
    transaction = db.begin_nested()
    seed_job_package(db, org_id, publish=True)
    transaction.rollback()
    assert rows(db, JobOpening, org_id) == []
    assert rows(db, KRA, org_id) == []
    assert len(rows(db, Position, org_id)) == 1


def test_rejects_wrong_tenant_and_keeps_other_org_records(marketing_db):
    db, org_id = marketing_db
    other_id = uuid4()
    other = Department(
        organization_id=other_id, department_code="MKT", department_name="Other org"
    )
    db.add(other)
    db.flush()
    seed_job_package(db, org_id)
    assert other.department_name == "Other org"
    assert (
        db.scalar(
            select(func.count())
            .select_from(JobOpening)
            .where(JobOpening.organization_id == other_id)
        )
        == 0
    )
    with pytest.raises(ValueError, match="tenant-scoped"):
        seed_job_package(db, other_id)
    db.get(Organization, org_id).organization_code = "OTHER"
    with pytest.raises(ValueError, match="Sherpackage"):
        seed_job_package(db, org_id)


def _hire_marketer(db, org_id):
    position = db.scalar(
        select(Position).where(
            Position.organization_id == org_id, Position.position_code == POSITION_CODE
        )
    )
    person = Person(
        organization_id=org_id,
        first_name="Test",
        last_name="Marketer",
        email=f"{uuid4().hex}@example.com",
    )
    db.add(person)
    db.flush()
    employee = Employee(
        organization_id=org_id,
        person_id=person.id,
        employee_code="SHP-MKT-TEST",
        designation_id=position.designation_id,
        department_id=position.department_id,
        date_of_joining=date(2026, 1, 1),
        status=EmployeeStatus.ACTIVE,
    )
    db.add(employee)
    db.flush()
    db.add(
        PositionAssignment(
            organization_id=org_id,
            employee_id=employee.employee_id,
            position_id=position.position_id,
            assignment_type=PositionAssignmentType.PRIMARY,
            start_date=date(2026, 1, 1),
        )
    )
    position.is_vacant = False
    db.flush()
    return employee


def test_kpis_require_real_incumbent_and_preserve_actual_results(marketing_db):
    db, org_id = marketing_db
    seed_job_package(db, org_id)
    employee = _hire_marketer(db, org_id)
    start = date(2026, 11, 1)
    end = start + timedelta(days=89)
    _, counts = seed_job_package(
        db,
        org_id,
        employee_code=employee.employee_code,
        period_start=start,
        period_end=end,
    )
    assert counts == {"kpi": 6}
    kpis = rows(db, KPI, org_id)
    assert sum(k.weightage for k in kpis) == Decimal("100")
    assert all(
        k.status == KPIStatus.DRAFT
        and k.actual_value is None
        and k.achievement_percentage is None
        for k in kpis
    )
    assert {k.target_value for k in kpis} == {Decimal(t.target) for t in TARGETS}
    kpis[0].actual_value = Decimal("5")
    kpis[0].target_value = Decimal("40")
    db.flush()
    _, counts = seed_job_package(
        db,
        org_id,
        employee_code=employee.employee_code,
        period_start=start,
        period_end=end,
    )
    assert counts == {}
    assert kpis[0].actual_value == Decimal("5")
    assert kpis[0].target_value == Decimal("40")


def test_cannot_publish_an_occupied_position(marketing_db):
    db, org_id = marketing_db
    seed_job_package(db, org_id)
    _hire_marketer(db, org_id)
    with pytest.raises(ValueError, match="occupied"):
        seed_job_package(db, org_id, publish=True)


def test_requires_valid_kpi_period_and_existing_employee(marketing_db):
    db, org_id = marketing_db
    with pytest.raises(ValueError, match="90-day"):
        seed_job_package(db, org_id, employee_code="NO-EMPLOYEE")
    with pytest.raises(ValueError, match="active Sherpackage"):
        with db.begin_nested():
            seed_job_package(
                db,
                org_id,
                employee_code="NO-EMPLOYEE",
                period_start=date(2026, 11, 1),
                period_end=date(2027, 1, 29),
            )
    assert rows(db, KPI, org_id) == []


def test_seed_requires_private_mode(marketing_db):
    db, org_id = marketing_db
    db.get(Organization, org_id).performance_mode = PerformanceMode.GOVERNMENT_PMS
    with pytest.raises(ValueError, match="PRIVATE"):
        seed_job_package(db, org_id)


def marker_for(db, org_id):
    return db.scalar(
        select(DomainSetting).where(
            DomainSetting.organization_id == org_id,
            DomainSetting.domain == SettingDomain.operations,
            DomainSetting.key == SEED_KEY,
        )
    )


@pytest.mark.parametrize("remove_job", [False, True])
def test_startup_seed_is_durable_and_never_recreates_or_reopens(
    marketing_db, remove_job
):
    db, org_id = marketing_db
    counts = seed_once(db, org_id)
    assert counts["job_opening"] == 1 and counts["job_published"] == 1
    marker = marker_for(db, org_id)
    assert marker.value_json["status"] == "OPEN"
    assert marker.scope == SettingScope.ORG_SPECIFIC
    assert marker.value_json["job_code"] == JOB_CODE
    db.commit()
    with Session(db.get_bind()) as restarted:
        restarted.info["organization_id"] = org_id
        job = rows(restarted, JobOpening, org_id)[0]
        if remove_job:
            restarted.delete(job)
        else:
            job.status = JobOpeningStatus.CLOSED
            job.description = "Edited by HR"
        restarted.commit()
        with patch(
            "scripts.seed_sherpackage_digital_marketer_on_start.seed_job_package"
        ) as seed:
            assert seed_once(restarted, org_id) is None
            seed.assert_not_called()
        remaining = rows(restarted, JobOpening, org_id)
        if remove_job:
            assert not remaining
        else:
            assert remaining[0].status == JobOpeningStatus.CLOSED
            assert remaining[0].description == "Edited by HR"


def test_startup_rollback_does_not_mark_complete_and_allows_retry(marketing_db):
    db, org_id = marketing_db
    with pytest.raises(RuntimeError, match="Failed transaction"):
        with db.begin_nested():
            seed_once(db, org_id)
            assert marker_for(db, org_id) is not None
            raise RuntimeError("Failed transaction")
    assert marker_for(db, org_id) is None
    assert rows(db, JobOpening, org_id) == []
    assert seed_once(db, org_id)["job_published"] == 1


def test_existing_manual_seed_gets_marker_without_overwriting_job(marketing_db):
    db, org_id = marketing_db
    job, _ = seed_job_package(db, org_id, publish=True)
    job.status = JobOpeningStatus.CLOSED
    job.description = "Reviewed description"
    db.flush()
    assert seed_once(db, org_id) == {}
    assert job.status == JobOpeningStatus.CLOSED
    assert job.description == "Reviewed description"
    assert marker_for(db, org_id).value_json["status"] == "CLOSED"


def test_startup_marker_cannot_skip_another_tenant(marketing_db):
    db, org_id = marketing_db
    db.add(
        DomainSetting(
            organization_id=uuid4(),
            domain=SettingDomain.operations,
            key=SEED_KEY,
            scope=SettingScope.ORG_SPECIFIC,
            value_type=SettingValueType.json,
            value_json={"completed": True},
        )
    )
    db.flush()
    assert seed_once(db, org_id)["job_opening"] == 1
    with pytest.raises(ValueError, match="tenant-scoped"):
        seed_once(db, uuid4())


def test_startup_seed_failure_has_no_completion_marker(marketing_db):
    db, org_id = marketing_db
    seed_job_package(db, org_id)
    _hire_marketer(db, org_id)
    with pytest.raises(ValueError, match="occupied"):
        with db.begin_nested():
            seed_once(db, org_id)
    assert marker_for(db, org_id) is None
    assert rows(db, JobOpening, org_id)[0].status == JobOpeningStatus.DRAFT


def test_startup_lock_precedes_marker_check():
    db = MagicMock()
    org_id = uuid4()
    db.info = {"organization_id": org_id}
    db.get_bind.return_value.dialect.name = "postgresql"
    db.scalar.return_value = object()
    assert seed_once(db, org_id) is None
    names = [call[0] for call in db.mock_calls]
    assert names.index("execute") < names.index("scalar")
    stmt = db.execute.call_args.args[0]
    assert "pg_advisory_xact_lock" in str(stmt)
    assert set(stmt.compile().params.values()) == {73421, org_id.int % (2**31)}


def test_startup_main_skips_missing_organization(capsys):
    from scripts import seed_sherpackage_digital_marketer_on_start as startup

    with (
        patch.object(startup, "cross_org_session") as cross,
        patch.object(startup, "session_for_org") as scoped,
    ):
        cross.return_value.__enter__.return_value.scalar.return_value = None
        startup.main()
    scoped.assert_not_called()
    assert "organization not found" in capsys.readouterr().out


def test_startup_main_commits_and_then_skips(marketing_db, capsys):
    from scripts import seed_sherpackage_digital_marketer_on_start as startup

    db, org_id = marketing_db
    with (
        patch.object(startup, "cross_org_session") as cross,
        patch.object(startup, "session_for_org") as scoped,
    ):
        cross.return_value.__enter__.return_value.scalar.return_value = org_id
        scoped.return_value.__enter__.return_value = db
        startup.main()
        startup.main()
    output = capsys.readouterr().out
    assert "startup seed completed" in output and "already completed" in output
    assert len(rows(db, JobOpening, org_id)) == 1


def test_seeded_opening_is_visible_after_another_tenants_recruitment_query(
    marketing_db,
):
    db, org_id = marketing_db
    db.commit()

    class TenantSession(Session):
        pass

    event.listen(TenantSession, "do_orm_execute", _add_org_filter)
    with TenantSession(db.get_bind()) as other:
        other_id = uuid4()
        other.info["organization_id"] = other_id
        assert RecruitmentService(other).list_job_openings(other_id).items == []

    event.listen(db, "do_orm_execute", _add_org_filter)
    try:
        assert seed_once(db, org_id)["job_published"] == 1
        db.commit()
    finally:
        event.remove(db, "do_orm_execute", _add_org_filter)

    with TenantSession(db.get_bind()) as restarted:
        restarted.info["organization_id"] = org_id
        result = RecruitmentService(restarted).list_job_openings(org_id)
        assert result.total == 1
        assert [job.job_code for job in result.items] == [JOB_CODE]
        assert result.items[0].status == JobOpeningStatus.OPEN
        assert result.items[0].department.department_name == "Marketing & Growth"
