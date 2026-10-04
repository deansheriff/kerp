from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

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
from app.models.person import Person
from scripts.seed_sherpackage_digital_marketer import (
    JOB_CODE,
    JOB_TEXT,
    POSITION_CODE,
    TARGETS,
    seed_job_package,
)

TABLE_MODELS = (
    Organization,
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
)


@pytest.fixture
def marketing_db():
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
                column.server_default = None
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
