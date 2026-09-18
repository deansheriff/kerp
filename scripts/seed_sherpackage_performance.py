#!/usr/bin/env python3
"""Add Sherpackage positions and clearly labelled sample performance records.

May run independently against an existing Sherpackage organization or as part
of seed_sherpackage.py. It never creates employees or sends notifications.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID, uuid5

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from sqlalchemy import and_, func, inspect, or_, select
from sqlalchemy.orm import Session

from app.db import Base
from app.db.session_context import cross_org_session, session_for_org
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
from app.models.people.perf.appraisal_cycle import AppraisalCycle, AppraisalCycleStatus
from app.models.people.perf.appraisal_template import (
    AppraisalTemplate,
    AppraisalTemplateKRA,
    AppraisalTemplateProfile,
)
from app.models.people.perf.kpi import KPI, KPIStatus
from app.models.people.perf.kra import KRA
from app.models.people.perf.scorecard import Scorecard, ScorecardItem
from app.services.people.hr.org_resolver import OrgResolver

SAMPLE = "Sample data for exploring Sherpackage performance workflows; not an actual staff evaluation."
WEIGHTS = (Decimal("50"), Decimal("30"), Decimal("20"))
T = TypeVar("T", bound=Base)


@dataclass(frozen=True)
class RoleSeed:
    code: str
    name: str
    department: str
    parent: str | None
    metrics: tuple[tuple[str, str, str], ...]  # name, target, unit (higher is better)
    employee_code: str | None = None


ROLES = (
    RoleSeed(
        "CEO",
        "Chief Executive Officer",
        "EXEC",
        None,
        (
            ("Quarterly strategic milestones delivered", "4", "milestones"),
            ("Customer renewal rate", "95", "%"),
            ("Leadership development sessions", "3", "sessions"),
        ),
        "SHP-0001",
    ),
    RoleSeed(
        "LEAD-ENG",
        "Lead Software Engineer",
        "ENG",
        "CEO",
        (
            ("Release commitments delivered", "90", "%"),
            ("Critical services with reviewed architecture", "4", "services"),
            ("Engineering mentoring sessions", "6", "sessions"),
        ),
        "SHP-0002",
    ),
    RoleSeed(
        "PM",
        "Product Manager",
        "PROD",
        "CEO",
        (
            ("Validated roadmap outcomes delivered", "4", "outcomes"),
            ("Customer discovery interviews", "12", "interviews"),
            ("Stakeholder product reviews", "3", "reviews"),
        ),
        "SHP-0003",
    ),
    RoleSeed(
        "DEVOPS",
        "DevOps Engineer",
        "OPS",
        "LEAD-ENG",
        (
            ("Production service availability", "99.9", "%"),
            ("Successful recovery exercises", "3", "exercises"),
            ("Operational runbooks validated", "6", "runbooks"),
        ),
        "SHP-0004",
    ),
    RoleSeed(
        "PEOPLE-FIN",
        "People & Finance Officer",
        "FINHR",
        "CEO",
        (
            ("Payroll runs reconciled on schedule", "3", "runs"),
            ("Employee records verified", "100", "%"),
            ("People and finance process improvements", "3", "improvements"),
        ),
        "SHP-0005",
    ),
    RoleSeed(
        "SWE",
        "Software Engineer",
        "ENG",
        "LEAD-ENG",
        (
            ("Accepted feature increments", "8", "increments"),
            ("Changed code covered by automated tests", "85", "%"),
            ("Engineering knowledge-sharing sessions", "3", "sessions"),
        ),
    ),
    RoleSeed(
        "QA",
        "Quality Assurance Engineer",
        "ENG",
        "LEAD-ENG",
        (
            ("Critical journeys with automated regression tests", "90", "%"),
            ("Release test plans completed", "6", "plans"),
            ("Exploratory testing workshops", "3", "workshops"),
        ),
    ),
    RoleSeed(
        "UX",
        "Product Designer",
        "PROD",
        "PM",
        (
            ("Validated user journey designs", "6", "designs"),
            ("Usability test task success rate", "85", "%"),
            ("Accessible design system components", "8", "components"),
        ),
    ),
    RoleSeed(
        "FRONTEND",
        "Frontend Engineer",
        "ENG",
        "LEAD-ENG",
        (
            ("Accepted responsive interface deliveries", "8", "deliveries"),
            ("Key pages passing accessibility checks", "95", "%"),
            ("Reusable interface components documented", "6", "components"),
        ),
    ),
    RoleSeed(
        "BACKEND",
        "Backend Engineer",
        "ENG",
        "LEAD-ENG",
        (
            ("Accepted API and integration deliveries", "8", "deliveries"),
            ("Critical endpoints covered by integration tests", "90", "%"),
            ("API contracts documented and reviewed", "6", "contracts"),
        ),
    ),
    RoleSeed(
        "DATA",
        "Data Engineer",
        "ENG",
        "LEAD-ENG",
        (
            ("Validated data pipelines delivered", "4", "pipelines"),
            ("Scheduled data quality checks passing", "99", "%"),
            ("Dataset ownership and lineage documented", "6", "datasets"),
        ),
    ),
    RoleSeed(
        "SEC",
        "Security Engineer",
        "OPS",
        "DEVOPS",
        (
            ("Critical remediation tasks completed within SLA", "95", "%"),
            ("Application threat models reviewed", "4", "reviews"),
            ("Security awareness workshops", "3", "workshops"),
        ),
    ),
)


class SeedWriter:
    """Insert missing seed identities, retaining user edits and stable IDs."""

    def __init__(self, db: Session, org_id: UUID):
        self.db = db
        self.org_id = org_id
        self.counts: Counter[str] = Counter()

    def ensure(
        self,
        model: type[T],
        identity: str,
        *,
        match: dict[str, Any] | None = None,
        **values: Any,
    ) -> tuple[T, bool]:
        pk = inspect(model).primary_key[0]
        seed_id = uuid5(
            self.org_id, f"sherpackage-performance-v1:{model.__tablename__}:{identity}"
        )
        condition = pk == seed_id
        if match:
            condition = or_(
                condition, and_(*(getattr(model, k) == v for k, v in match.items()))
            )
        row = self.db.scalar(
            select(model).where(
                inspect(model).columns["organization_id"] == self.org_id,
                condition,
            )
        )
        if row is not None:
            return row, False
        row = model(
            **{pk.key: seed_id}, organization_id=self.org_id, **(match or {}), **values
        )
        self.db.add(row)
        self.db.flush()
        self.counts[model.__tablename__] += 1
        return row, True


def _seed_catalog(writer: SeedWriter) -> dict[str, tuple[AppraisalTemplate, list[KRA]]]:
    db, org_id = writer.db, writer.org_id
    positions: dict[str, Position] = {}
    catalog: dict[str, tuple[AppraisalTemplate, list[KRA]]] = {}
    departments = {
        d.department_code: d
        for d in db.scalars(
            select(Department).where(Department.organization_id == org_id)
        )
    }
    missing = {role.department for role in ROLES} - departments.keys()
    if missing:
        raise ValueError(
            f"Run seed_sherpackage.py first; missing departments: {', '.join(sorted(missing))}"
        )

    for role in ROLES:
        department = departments[role.department]
        designation, _ = writer.ensure(
            Designation,
            role.code,
            match={"designation_code": role.code},
            designation_name=role.name,
            description=f"Sherpackage {role.name} role.",
            is_active=True,
        )
        position, created = writer.ensure(
            Position,
            role.code,
            match={"position_code": f"SHP-{role.code}"},
            position_name=role.name,
            department_id=department.department_id,
            designation_id=designation.designation_id,
            parent_position_id=positions[role.parent].position_id
            if role.parent
            else None,
            is_active=True,
            is_vacant=True,
        )
        positions[role.code] = position
        if role.employee_code and created:
            employee = db.scalar(
                select(Employee).where(
                    Employee.organization_id == org_id,
                    Employee.employee_code == role.employee_code,
                    Employee.designation_id == designation.designation_id,
                    Employee.status == EmployeeStatus.ACTIVE,
                )
            )
            if employee:
                # Never replace an existing (including historical or future) assignment.
                assignment = db.scalar(
                    select(PositionAssignment).where(
                        PositionAssignment.organization_id == org_id,
                        PositionAssignment.employee_id == employee.employee_id,
                    )
                )
                if assignment is None:
                    writer.ensure(
                        PositionAssignment,
                        role.code,
                        employee_id=employee.employee_id,
                        position_id=position.position_id,
                        assignment_type=PositionAssignmentType.PRIMARY,
                        start_date=employee.date_of_joining,
                    )
                    position.is_vacant = False

        kras = []
        for idx, (name, target, unit) in enumerate(role.metrics):
            kra, _ = writer.ensure(
                KRA,
                f"{role.code}-{idx}",
                match={"kra_code": f"SHP-{role.code}-{idx + 1}"},
                kra_name=name,
                department_id=department.department_id,
                designation_id=designation.designation_id,
                default_weightage=WEIGHTS[idx],
                category="PERFORMANCE" if idx < 2 else "LEARNING",
                description=f"Quarterly outcome for {role.name}.",
                measurement_criteria=f"Target: {target} {unit} per quarter. Higher is better. Verify against team delivery records.",
                is_active=True,
            )
            kras.append(kra)
        template, created = writer.ensure(
            AppraisalTemplate,
            role.code,
            match={"template_code": f"SHP-{role.code}"},
            template_name=f"{role.name} - Quarterly Review",
            description="Assess delivery (50%), quality and stakeholder outcomes (30%), and development (20%). Ratings: 1 Poor, 2 Fair, 3 Good, 4 Excellent, 5 Outstanding.",
            department_id=department.department_id,
            designation_id=designation.designation_id,
            template_profile=AppraisalTemplateProfile.PRIVATE,
            rating_scale_max=5,
            is_active=True,
        )
        if created:
            for idx, kra in enumerate(kras):
                writer.ensure(
                    AppraisalTemplateKRA,
                    f"{role.code}-{idx}",
                    template_id=template.template_id,
                    kra_id=kra.kra_id,
                    weightage=WEIGHTS[idx],
                    sequence=idx,
                )
        catalog[role.code] = template, kras
    db.flush()
    return catalog


def _seed_employee_period(
    writer: SeedWriter,
    employee: Employee,
    role: RoleSeed,
    template: AppraisalTemplate,
    kras: list[KRA],
    cycle: AppraisalCycle,
    *,
    completed: bool,
) -> None:
    db, org_id = writer.db, writer.org_id
    identity = f"{cycle.cycle_id}:{employee.employee_id}"
    actuals = []
    for idx, (name, target, unit) in enumerate(role.metrics):
        target_value = Decimal(target)
        ratio = Decimal(
            ("1.0", "0.9", "1.0")[idx] if completed else ("0.8", "0.7", "0.5")[idx]
        )
        actual = (target_value * ratio).quantize(
            Decimal("0.01") if unit == "%" else Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        if role.code == "DEVOPS" and idx == 0:
            actual = Decimal("99.95" if completed else "99.87")
        actuals.append(actual)
        writer.ensure(
            KPI,
            f"{identity}:{idx}",
            employee_id=employee.employee_id,
            kra_id=kras[idx].kra_id,
            kpi_name=f"[Sample] {name}",
            description=SAMPLE,
            period_start=cycle.review_period_start,
            period_end=cycle.review_period_end,
            target_value=target_value,
            actual_value=actual,
            unit_of_measure=unit,
            achievement_percentage=(actual / target_value * 100).quantize(
                Decimal("0.01")
            ),
            weightage=WEIGHTS[idx],
            status=(KPIStatus.ACHIEVED if actual >= target_value else KPIStatus.MISSED)
            if completed
            else (KPIStatus.AT_RISK if idx == 2 else KPIStatus.ON_TRACK),
            notes=SAMPLE,
        )

    scorecard, created = writer.ensure(
        Scorecard,
        identity,
        employee_id=employee.employee_id,
        period_start=cycle.review_period_start,
        period_end=cycle.review_period_end,
        period_label=f"[Sample] 2026 Q{cycle.quarter}",
        summary=SAMPLE,
        is_finalized=completed,
        finalized_on=cycle.end_date if completed else None,
    )
    if created:
        total = Decimal("0")
        for idx, (name, target, unit) in enumerate(role.metrics):
            score = min(Decimal("100"), actuals[idx] / Decimal(target) * 100).quantize(
                Decimal("0.01")
            )
            weighted = (score * WEIGHTS[idx] / 100).quantize(Decimal("0.01"))
            total += weighted
            writer.ensure(
                ScorecardItem,
                f"{identity}:{idx}",
                scorecard_id=scorecard.scorecard_id,
                perspective=("PROCESS", "CUSTOMER", "LEARNING")[idx],
                metric_name=name,
                description=SAMPLE,
                target_value=Decimal(target),
                actual_value=actuals[idx],
                unit_of_measure=unit,
                weightage=WEIGHTS[idx],
                score=score,
                weighted_score=weighted,
                sequence=idx,
                status="ACHIEVED" if actuals[idx] >= Decimal(target) else "AT_RISK",
            )
            setattr(
                scorecard,
                ("process_score", "customer_score", "learning_score")[idx],
                weighted,
            )
        scorecard.overall_score = total
        if completed:
            scorecard.overall_rating = 5
            scorecard.rating_label = "Exceptional"

    manager = OrgResolver(db).get_manager(
        employee.employee_id,
        org_id,
        as_of=cycle.review_period_end if completed else date.today(),
    )
    if manager is None or manager.employee_id == employee.employee_id:
        return  # Do not fabricate a reviewer for the chief executive.
    appraisal, created = writer.ensure(
        Appraisal,
        identity,
        match={"employee_id": employee.employee_id, "cycle_id": cycle.cycle_id},
        template_id=template.template_id,
        manager_id=manager.employee_id,
        status=AppraisalStatus.COMPLETED
        if completed
        else AppraisalStatus.SELF_ASSESSMENT,
        self_summary=SAMPLE,
        self_overall_rating=4 if completed else None,
        self_assessment_date=date(2026, 7, 3) if completed else None,
        manager_summary=SAMPLE if completed else None,
        manager_overall_rating=4 if completed else None,
        manager_review_date=date(2026, 7, 8) if completed else None,
        calibration_date=date(2026, 7, 10) if completed else None,
        calibrated_rating=4 if completed else None,
        final_score=Decimal("4.00") if completed else None,
        final_rating=4 if completed else None,
        rating_label="Excellent" if completed else None,
        completed_on=cycle.end_date if completed else None,
        development_needs="[Sample] Agree one focused development activity with the reviewer.",
    )
    if not created:
        return
    for idx, kra in enumerate(kras):
        writer.ensure(
            AppraisalKRAScore,
            f"{identity}:{idx}",
            appraisal_id=appraisal.appraisal_id,
            kra_id=kra.kra_id,
            weightage=WEIGHTS[idx],
            self_rating=4 if completed else None,
            manager_rating=4 if completed else None,
            final_rating=4 if completed else None,
            weighted_score=WEIGHTS[idx] * Decimal("4") / 100 if completed else None,
            self_comments=SAMPLE if completed else None,
            manager_comments=SAMPLE if completed else None,
        )
    peer = db.scalar(
        select(Employee)
        .where(
            Employee.organization_id == org_id,
            Employee.employee_code.in_(
                [r.employee_code for r in ROLES if r.employee_code]
            ),
            Employee.employee_id.not_in([employee.employee_id, manager.employee_id]),
            Employee.status == EmployeeStatus.ACTIVE,
        )
        .order_by(Employee.employee_code)
    )
    if peer:
        writer.ensure(
            AppraisalFeedback,
            identity,
            appraisal_id=appraisal.appraisal_id,
            feedback_from_id=peer.employee_id,
            feedback_type="PEER",
            is_anonymous=False,
            overall_rating=4 if completed else None,
            strengths="[Sample] Communicates delivery progress and supports colleagues."
            if completed
            else None,
            areas_for_improvement="[Sample] Share decisions and handover notes earlier."
            if completed
            else None,
            general_comments=SAMPLE,
            submitted_on=date(2026, 7, 5) if completed else None,
        )


def seed_performance(db: Session, org_id: UUID) -> dict[str, int]:
    """Seed within the caller's tenant transaction; commit only at the entry point."""
    if db.info.get("organization_id") != org_id or db.info.get("allow_cross_org"):
        raise ValueError(
            "Performance seeding requires a matching tenant-scoped session"
        )
    organization = db.scalar(
        select(Organization).where(Organization.organization_id == org_id)
    )
    if not organization or organization.organization_code != "SHP":
        raise ValueError(
            "Performance seed is restricted to the Sherpackage (SHP) organization"
        )
    if organization.performance_mode != PerformanceMode.PRIVATE:
        raise ValueError(
            "Sherpackage performance seed requires PRIVATE performance mode"
        )
    if db.get_bind().dialect.name == "postgresql":
        # Serialize startup replicas without changing schema or relaxing constraints.
        db.execute(select(func.pg_advisory_xact_lock(73421, org_id.int % (2**31))))
    writer = SeedWriter(db, org_id)
    catalog = _seed_catalog(writer)
    for quarter, completed in ((2, True), (3, False)):
        cycle, _ = writer.ensure(
            AppraisalCycle,
            f"2026-Q{quarter}",
            match={"cycle_code": f"SHP-SAMPLE-2026-Q{quarter}"},
            cycle_name=f"[Sample] Sherpackage 2026 Q{quarter} Review",
            description=SAMPLE,
            review_period_start=date(2026, 4 if completed else 7, 1),
            review_period_end=date(2026, 6 if completed else 9, 30),
            start_date=date(2026, 7 if completed else 9, 1),
            end_date=date(2026, 7 if completed else 10, 15),
            self_assessment_deadline=date(2026, 7 if completed else 10, 5),
            manager_review_deadline=date(2026, 7 if completed else 10, 10),
            calibration_deadline=date(2026, 7 if completed else 10, 15),
            cycle_type="QUARTERLY",
            quarter=quarter,
            min_tenure_months=3,
            status=AppraisalCycleStatus.COMPLETED
            if completed
            else AppraisalCycleStatus.ACTIVE,
        )
        for role in ROLES:
            if not role.employee_code:
                continue
            template, kras = catalog[role.code]
            employee = db.scalar(
                select(Employee).where(
                    Employee.organization_id == org_id,
                    Employee.employee_code == role.employee_code,
                    Employee.designation_id == template.designation_id,
                    Employee.status == EmployeeStatus.ACTIVE,
                )
            )
            if employee:
                _seed_employee_period(
                    writer, employee, role, template, kras, cycle, completed=completed
                )
    db.flush()
    return dict(writer.counts)


def main() -> None:
    from scripts.seed_sherpackage import _sherpackage_org_id

    with cross_org_session() as db:
        org = db.scalar(
            select(Organization).where(
                Organization.organization_id == _sherpackage_org_id(),
                Organization.organization_code == "SHP",
            )
        )
        if org is None:
            org = db.scalar(
                select(Organization).where(Organization.organization_code == "SHP")
            )
        if org is None:
            raise ValueError(
                "Sherpackage does not exist; run scripts/seed_sherpackage.py first"
            )
        org_id = org.organization_id
    with session_for_org(org_id) as db:
        counts = seed_performance(db, org_id)
        db.commit()
    print(f"Sherpackage performance seed completed ({org_id})")
    print(f"Records added: {sum(counts.values())}")
    for name, count in counts.items():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
