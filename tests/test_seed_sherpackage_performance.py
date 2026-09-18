"""Database-backed regression tests for the additive Sherpackage seed."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

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
from app.models.people.perf.appraisal import (
    Appraisal,
    AppraisalFeedback,
    AppraisalKRAScore,
    AppraisalStatus,
)
from app.models.people.perf.appraisal_cycle import AppraisalCycle
from app.models.people.perf.appraisal_template import (
    AppraisalTemplate,
    AppraisalTemplateKRA,
)
from app.models.people.perf.kpi import KPI
from app.models.people.perf.kra import KRA
from app.models.people.perf.scorecard import Scorecard, ScorecardItem
from app.models.person import Person
from app.services.people.hr.org_resolver import OrgResolver
from app.services.people.perf.perf_service import PerformanceService
from scripts.seed_sherpackage import (
    _seed_departments,
    _seed_designations,
    _seed_employees,
)
from scripts.seed_sherpackage_performance import ROLES, seed_performance

MODELS = (
    Organization,
    Department,
    Designation,
    Employee,
    Position,
    PositionAssignment,
    KRA,
    AppraisalTemplate,
    AppraisalTemplateKRA,
    AppraisalCycle,
    KPI,
    Appraisal,
    AppraisalKRAScore,
    AppraisalFeedback,
    Scorecard,
    ScorecardItem,
)


@pytest.fixture
def seed_db(db_session):
    for model in MODELS:
        for column in model.__table__.columns:
            if column.server_default is not None and "gen_random_uuid" in str(
                column.server_default.arg
            ):
                column.server_default = None
        model.__table__.create(db_session.get_bind(), checkfirst=True)
    org_id = uuid4()
    db_session.info["organization_id"] = org_id
    db_session.add(
        Organization(
            organization_id=org_id,
            organization_code="SHP",
            legal_name="Sherpackage",
            functional_currency_code="NGN",
            presentation_currency_code="NGN",
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
            performance_mode=PerformanceMode.PRIVATE,
        )
    )
    db_session.flush()
    departments = _seed_departments(db_session)
    designations = _seed_designations(db_session)
    for role in ROLES:
        if not role.employee_code:
            continue
        person = Person(
            organization_id=org_id,
            first_name=role.employee_code,
            last_name="Sample",
            email=f"{uuid4().hex}@example.com",
        )
        db_session.add(person)
        db_session.flush()
        db_session.add(
            Employee(
                organization_id=org_id,
                person_id=person.id,
                employee_code=role.employee_code,
                department_id=departments[role.department].department_id,
                designation_id=designations[role.code].designation_id,
                date_of_joining=date(2025, 1, 1),
                status=EmployeeStatus.ACTIVE,
            )
        )
    db_session.flush()
    return db_session, org_id


def _rows(db, model, org_id):
    return list(db.scalars(select(model).where(model.organization_id == org_id)))


def test_seed_populates_linked_private_performance_screens(seed_db):
    db, org_id = seed_db
    counts = seed_performance(db, org_id)
    assert counts["position"] == 12
    assert len(_rows(db, Employee, org_id)) == 5
    assert len(_rows(db, Designation, org_id)) == 12
    assert len(_rows(db, PositionAssignment, org_id)) == 5
    assert sum(p.is_vacant for p in _rows(db, Position, org_id)) == 7
    assert len(_rows(db, KRA, org_id)) == 36
    assert len(_rows(db, AppraisalTemplate, org_id)) == 12
    assert len(_rows(db, AppraisalCycle, org_id)) == 2
    assert len(_rows(db, KPI, org_id)) == 30
    assert len(_rows(db, Appraisal, org_id)) == 8
    assert len(_rows(db, AppraisalFeedback, org_id)) == 8
    assert len(_rows(db, Scorecard, org_id)) == 10

    for template in _rows(db, AppraisalTemplate, org_id):
        assert len(template.kras) == 3
        assert sum(k.weightage for k in template.kras) == Decimal("100")
        assert all(
            k.kra.designation_id == template.designation_id for k in template.kras
        )
    employees = {e.employee_code: e for e in _rows(db, Employee, org_id)}
    manager = OrgResolver(db).get_manager(employees["SHP-0004"].employee_id, org_id)
    assert manager.employee_id == employees["SHP-0002"].employee_id
    for appraisal in _rows(db, Appraisal, org_id):
        assert appraisal.employee_id != appraisal.manager_id
        assert len(appraisal.kra_scores) == 3
        assert sum(s.weightage for s in appraisal.kra_scores) == Decimal("100")
        if appraisal.status == AppraisalStatus.COMPLETED:
            assert appraisal.final_score == sum(
                s.weighted_score for s in appraisal.kra_scores
            )
            assert appraisal.completed_on >= appraisal.manager_review_date
        else:
            assert appraisal.final_rating is None
    for kpi in _rows(db, KPI, org_id):
        assert kpi.achievement_percentage == kpi.calculate_achievement().quantize(
            Decimal("0.01")
        )
        assert (
            kpi.kra.organization_id
            == kpi.organization_id
            == kpi.employee.organization_id
        )
    for card in _rows(db, Scorecard, org_id):
        assert len(card.items) == 3
        assert card.overall_score == sum(i.weighted_score for i in card.items)

    stats = PerformanceService(db).get_performance_stats(org_id)
    assert stats["active_cycles"] == 1
    assert stats["average_rating"] == Decimal("4.0")


def test_rerun_preserves_edited_rows_and_does_not_duplicate(seed_db):
    db, org_id = seed_db
    seed_performance(db, org_id)
    before = {model: len(_rows(db, model, org_id)) for model in MODELS}
    employee = _rows(db, Employee, org_id)[0]
    employee.person.first_name = "Updated name"
    employee.person.email = f"edited-{uuid4().hex}@sherpackageonline.com"
    employee.ctc = Decimal("123456")
    employee.status = EmployeeStatus.ON_LEAVE
    template = _rows(db, AppraisalTemplate, org_id)[0]
    template.template_name = "HR custom review"
    template.template_code = "RENAMED-TEMPLATE"
    kra = _rows(db, KRA, org_id)[0]
    kra.measurement_criteria = "HR custom criteria"
    kpi = _rows(db, KPI, org_id)[0]
    kpi.kpi_name = "Custom goal name"
    kpi.actual_value = Decimal("12")
    appraisal = _rows(db, Appraisal, org_id)[0]
    appraisal.self_summary = "Employee edited summary"
    card = _rows(db, Scorecard, org_id)[0]
    card.summary = "Edited scorecard summary"
    db.flush()

    _seed_employees(
        db,
        departments={},
        designations={},
        employment_types={},
        grades={},
        locations={},
        shifts={},
    )
    assert seed_performance(db, org_id) == {}
    assert before == {model: len(_rows(db, model, org_id)) for model in MODELS}
    db.expire_all()
    assert employee.person.first_name == "Updated name"
    assert employee.ctc == Decimal("123456")
    assert employee.status == EmployeeStatus.ON_LEAVE
    assert template.template_name == "HR custom review"
    assert kra.measurement_criteria == "HR custom criteria"
    assert kpi.actual_value == Decimal("12")
    assert appraisal.self_summary == "Employee edited summary"
    assert card.summary == "Edited scorecard summary"


def test_existing_position_assignments_are_not_replaced(seed_db):
    db, org_id = seed_db
    employee = _rows(db, Employee, org_id)[0]
    position = Position(
        organization_id=org_id,
        position_code="CUSTOM",
        position_name="Existing role",
        is_vacant=False,
    )
    db.add(position)
    db.flush()
    assignment = PositionAssignment(
        organization_id=org_id,
        employee_id=employee.employee_id,
        position_id=position.position_id,
        assignment_type=PositionAssignmentType.PRIMARY,
        start_date=date(2025, 1, 1),
    )
    db.add(assignment)
    db.flush()
    seed_performance(db, org_id)
    assignments = [
        a
        for a in _rows(db, PositionAssignment, org_id)
        if a.employee_id == employee.employee_id
    ]
    assert assignments == [assignment]
    assert assignment.position_id == position.position_id


def test_base_catalog_preserves_hr_edits(seed_db):
    db, org_id = seed_db
    department = _rows(db, Department, org_id)[0]
    designation = _rows(db, Designation, org_id)[0]
    department.department_name = "Updated department"
    department.is_active = False
    designation.designation_name = "Updated designation"
    designation.is_active = False
    db.flush()
    _seed_departments(db)
    _seed_designations(db)
    db.flush()
    db.expire_all()
    assert department.department_name == "Updated department"
    assert department.is_active is False
    assert designation.designation_name == "Updated designation"
    assert designation.is_active is False


def test_seed_does_not_touch_other_tenant_rows(seed_db):
    db, org_id = seed_db
    other_org = uuid4()
    other = Designation(
        organization_id=other_org,
        designation_code="CEO",
        designation_name="Other CEO",
    )
    db.add(other)
    db.flush()
    seed_performance(db, org_id)
    assert other.designation_name == "Other CEO"
    assert (
        db.scalar(
            select(func.count())
            .select_from(KPI)
            .where(KPI.organization_id == other_org)
        )
        == 0
    )
    assert all(
        d.designation_id != other.designation_id for d in _rows(db, Designation, org_id)
    )
    with pytest.raises(ValueError, match="tenant-scoped"):
        seed_performance(db, other_org)


def test_seed_rejects_wrong_org_and_non_private_mode(seed_db):
    db, org_id = seed_db
    org = db.get(Organization, org_id)
    org.organization_code = "NOT-SHP"
    with pytest.raises(ValueError, match="restricted"):
        seed_performance(db, org_id)
    org.organization_code = "SHP"
    org.performance_mode = PerformanceMode.GOVERNMENT_PMS
    with pytest.raises(ValueError, match="PRIVATE"):
        seed_performance(db, org_id)
    assert _rows(db, Position, org_id) == []


def test_seed_rolls_back_as_one_transaction(seed_db):
    db, org_id = seed_db
    with pytest.raises(RuntimeError, match="Simulated failure"):
        with db.begin_nested():
            seed_performance(db, org_id)
            raise RuntimeError("Simulated failure")
    assert _rows(db, Position, org_id) == []
    assert _rows(db, Appraisal, org_id) == []
    assert seed_performance(db, org_id)["position"] == 12
