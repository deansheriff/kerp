#!/usr/bin/env python3
"""Prepare Sherpackage's Abuja vacancy; publish only with --publish.

The startup wrapper publishes this package once and records database completion.
Manual runs preserve existing vacancies and ratings. Employee KPIs are optional
and require an existing position incumbent.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session_context import cross_org_session, session_for_org
from app.models.finance.core_org.organization import Organization, PerformanceMode
from app.models.people.hr import (
    Department,
    Designation,
    Employee,
    EmployeeStatus,
    Position,
)
from app.models.people.perf.appraisal_template import (
    AppraisalTemplate,
    AppraisalTemplateKRA,
    AppraisalTemplateProfile,
)
from app.models.people.perf.kpi import KPI, KPIStatus
from app.models.people.perf.kra import KRA
from app.models.people.recruit.job_opening import JobOpening, JobOpeningStatus
from app.services.people.hr.org_resolver import OrgResolver
from app.services.people.recruit.recruit_service import RecruitmentService
from scripts.seed_sherpackage_performance import SeedWriter

JOB_CODE = "SHP-DM-2026-001"
ROLE_CODE = "DIGITAL-MKT"
POSITION_CODE = "SHP-DIGITAL-MKT"
TEMPLATE_CODE = "SHP-DM-90DAY"
JOB_TEXT = Path(__file__).with_name("data") / "sherpackage_digital_marketer.txt"


@dataclass(frozen=True)
class MarketingTarget:
    code: str
    area: str
    name: str
    target: str
    unit: str
    weight: str
    evidence: str


TARGETS = (
    MarketingTarget(
        "LEADS",
        "Qualified demand generation",
        "Sales-accepted marketing leads",
        "30",
        "leads",
        "30",
        "Distinct CRM leads accepted by sales against agreed customer-fit and need criteria. Exclude spam, duplicates, and unqualified contacts.",
    ),
    MarketingTarget(
        "DEMOS",
        "Pipeline contribution",
        "Completed marketing-sourced product demos",
        "12",
        "demos",
        "20",
        "CRM meetings actually held with qualified prospects and verified marketing attribution. Exclude cancellations, no-shows, and duplicate meetings.",
    ),
    MarketingTarget(
        "CONTENT",
        "Content and organic discovery",
        "Approved original content assets published",
        "12",
        "assets",
        "15",
        "Published original articles, case studies, videos, or landing pages passing the agreed quality review. Do not count cross-posts or minor edits again.",
    ),
    MarketingTarget(
        "DELIVERY",
        "Campaign delivery",
        "Approved campaign milestones delivered on time",
        "90",
        "%",
        "15",
        "On-time completed milestones divided by milestones due, multiplied by 100. Freeze deadlines with the manager; document approved scope changes. No milestones due means not applicable, not 100%.",
    ),
    MarketingTarget(
        "TRACKING",
        "Measurement and attribution",
        "Live campaigns passing tracking checks",
        "100",
        "%",
        "10",
        "Audited live campaigns with valid source tags, verified conversion events, and CRM source capture divided by campaigns audited, multiplied by 100. No live campaigns means not applicable.",
    ),
    MarketingTarget(
        "TESTING",
        "Experimentation and learning",
        "Documented marketing experiments completed",
        "3",
        "experiments",
        "10",
        "Experiments with a hypothesis, baseline, adequate observation period, findings, and a next-step decision. A well-documented negative or inconclusive result still counts.",
    ),
)


def seed_job_package(
    db: Session,
    org_id: UUID,
    *,
    publish: bool = False,
    employee_code: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[JobOpening, dict[str, int]]:
    """Flush the requested package; the caller owns commit or rollback."""
    if db.info.get("organization_id") != org_id or db.info.get("allow_cross_org"):
        raise ValueError("A matching tenant-scoped session is required")
    org = db.scalar(select(Organization).where(Organization.organization_id == org_id))
    if not org or org.organization_code != "SHP":
        raise ValueError("This package is only for the Sherpackage (SHP) organization")
    if org.performance_mode != PerformanceMode.PRIVATE:
        raise ValueError("This appraisal template requires PRIVATE performance mode")
    if employee_code:
        if not period_start or not period_end or (period_end - period_start).days != 89:
            raise ValueError(
                "Employee KPI targets require an explicit 90-day inclusive period"
            )
    elif period_start or period_end:
        raise ValueError("Supply an employee code with the KPI period")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(73421, org_id.int % (2**31))))

    writer = SeedWriter(db, org_id)
    department, _ = writer.ensure(
        Department,
        "DM-MARKETING",
        match={"department_code": "MKT"},
        department_name="Marketing & Growth",
        description="Product marketing, qualified demand generation, and marketing analytics.",
        is_active=True,
    )
    designation, _ = writer.ensure(
        Designation,
        "DM-DESIGNATION",
        match={"designation_code": ROLE_CODE},
        designation_name="Digital Marketer",
        description="B2B software and technology marketing.",
        is_active=True,
    )
    ceo_position = db.scalar(
        select(Position).where(
            Position.organization_id == org_id,
            Position.position_code == "SHP-CEO",
            Position.is_active.is_(True),
        )
    )
    if ceo_position is None:
        raise ValueError(
            "Create or confirm Sherpackage's SHP-CEO position before seeding this vacancy"
        )
    position, _ = writer.ensure(
        Position,
        "DM-POSITION",
        match={"position_code": POSITION_CODE},
        position_name="Digital Marketer",
        department_id=department.department_id,
        designation_id=designation.designation_id,
        parent_position_id=ceo_position.position_id,
        is_vacant=True,
        is_active=True,
    )
    kras = []
    for target in TARGETS:
        kra, _ = writer.ensure(
            KRA,
            f"DM-{target.code}",
            match={"kra_code": f"SHP-DM-{target.code}"},
            kra_name=target.area,
            department_id=department.department_id,
            designation_id=designation.designation_id,
            category="PERFORMANCE",
            default_weightage=Decimal(target.weight),
            is_active=True,
            description=f"{target.name}. Proposed 90-day target: {target.target} {target.unit}.",
            measurement_criteria=f"{target.evidence} Confirm the target against baseline, approved budget, and resources with the manager before assigning it.",
        )
        kras.append(kra)
    template, created = writer.ensure(
        AppraisalTemplate,
        "DM-TEMPLATE",
        match={"template_code": TEMPLATE_CODE},
        template_name="Digital Marketer - 90-day Review",
        department_id=department.department_id,
        designation_id=designation.designation_id,
        template_profile=AppraisalTemplateProfile.PRIVATE,
        rating_scale_max=5,
        is_active=True,
        description="Evidence-based marketing review. Weights: demand 30%, demos 20%, content 15%, delivery 15%, tracking 10%, experimentation 10%. Ratings 1-5 require manager judgment; KPI achievement does not automatically set appraisal scores. Agree targets before the period; do not treat these proposed targets as historical results.",
    )
    if created:
        for idx, (target, kra) in enumerate(zip(TARGETS, kras, strict=True)):
            writer.ensure(
                AppraisalTemplateKRA,
                f"DM-{target.code}",
                template_id=template.template_id,
                kra_id=kra.kra_id,
                weightage=Decimal(target.weight),
                sequence=idx,
            )

    service = RecruitmentService(db)
    opening = db.scalar(
        select(JobOpening).where(
            JobOpening.organization_id == org_id,
            JobOpening.job_code == JOB_CODE,
        )
    )
    if opening is None:
        opening = service.create_job_opening(
            org_id,
            job_code=JOB_CODE,
            job_title="Digital Marketer",
            department_id=department.department_id,
            designation_id=designation.designation_id,
            position_id=position.position_id,
            number_of_positions=1,
            employment_type="FULL_TIME",
            location="Abuja, Nigeria",
            is_remote=False,
            currency_code=org.functional_currency_code,
            min_experience_years=2,
            description=JOB_TEXT.read_text(encoding="utf-8").strip(),
            required_skills="B2B copywriting, Content planning, SEO, Social media management, Paid campaign management, Google Analytics 4, Conversion tracking, Email marketing, CRM lead handover, Spreadsheet reporting, Budget management",
            preferred_skills="Software or SaaS marketing, LinkedIn campaigns, Google Ads, Meta Ads Manager, Google Search Console, Google Tag Manager, Marketing automation, Canva or Figma, Video editing",
            education_requirements="Marketing, communications, business or a related qualification; equivalent practical experience and a strong portfolio are equally considered.",
        )
        writer.counts["job_opening"] += 1
    if publish and opening.status == JobOpeningStatus.DRAFT:
        if opening.position_id != position.position_id or not position.is_active:
            raise ValueError("Review the opening's linked position before publishing")
        if not position.is_vacant or OrgResolver(db).get_position_incumbent(
            position.position_id, org_id
        ):
            raise ValueError(
                "Cannot publish: the Digital Marketer position is already occupied"
            )
        service.publish_job_opening(org_id, opening.job_opening_id)
        writer.counts["job_published"] += 1

    if employee_code:
        employee = db.scalar(
            select(Employee).where(
                Employee.organization_id == org_id,
                Employee.employee_code == employee_code,
                Employee.status == EmployeeStatus.ACTIVE,
                Employee.designation_id == designation.designation_id,
            )
        )
        if employee is None:
            raise ValueError("Employee must be an active Sherpackage Digital Marketer")
        assignment = OrgResolver(db).get_active_assignment(employee.employee_id, org_id)
        if not assignment or assignment.position_id != position.position_id:
            raise ValueError(
                "Assign the employee to the Digital Marketer position in HR first"
            )
        for target, kra in zip(TARGETS, kras, strict=True):
            writer.ensure(
                KPI,
                f"DM:{employee.employee_id}:{period_start}:{period_end}:{target.code}",
                employee_id=employee.employee_id,
                kra_id=kra.kra_id,
                kpi_name=target.name,
                period_start=period_start,
                period_end=period_end,
                target_value=Decimal(target.target),
                unit_of_measure=target.unit,
                weightage=Decimal(target.weight),
                status=KPIStatus.DRAFT,
                description=target.evidence,
                notes="Proposed target: manager and employee must confirm baseline, budget, resources, and measurement before activation. No actual result has been recorded.",
            )
    db.flush()
    return opening, dict(writer.counts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", type=UUID)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish a draft vacancy to the careers portal",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show counts, then roll back",
    )
    parser.add_argument(
        "--employee-code",
        help="Optional: assign draft KPIs to an existing hired marketer",
    )
    parser.add_argument("--period-start", type=date.fromisoformat)
    parser.add_argument("--period-end", type=date.fromisoformat)
    args = parser.parse_args()
    with cross_org_session() as db:
        query = select(Organization).where(Organization.organization_code == "SHP")
        if args.organization_id:
            query = query.where(Organization.organization_id == args.organization_id)
        org = db.scalar(query)
        if org is None:
            raise ValueError(
                "Sherpackage was not found; no organization or employees will be created"
            )
        org_id = org.organization_id
        slug = org.slug
    with session_for_org(org_id) as db:
        opening, counts = seed_job_package(
            db,
            org_id,
            publish=args.publish,
            employee_code=args.employee_code,
            period_start=args.period_start,
            period_end=args.period_end,
        )
        status = opening.status.value
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    print(
        "DRY RUN: all changes rolled back"
        if args.dry_run
        else "Digital Marketer package saved"
    )
    print(f"Organization: {org_id}; opening: {JOB_CODE}; status: {status}")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    if not counts:
        print("  No changes; existing records were preserved.")
    if status == JobOpeningStatus.OPEN.value and slug and not args.dry_run:
        print(f"Careers path: /careers/{slug}/jobs/{JOB_CODE}")


if __name__ == "__main__":
    main()
