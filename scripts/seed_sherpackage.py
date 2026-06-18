#!/usr/bin/env python3
"""Seed an idempotent Sherpackage technology company organization."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from app.db.session_context import cross_org_session, session_for_org
from app.models.auth import AuthProvider, UserCredential
from app.models.finance.core_org.location import Location, LocationType
from app.models.finance.core_org.organization import (
    AccountingFramework,
    Organization,
    PerformanceMode,
    SectorType,
)
from app.models.people.attendance.shift_type import ShiftType
from app.models.people.hr import (
    Department,
    Designation,
    Employee,
    EmployeeGrade,
    EmployeeStatus,
    EmploymentType,
)
from app.models.people.hr.employee import Gender as EmployeeGender
from app.models.people.hr.employee import SalaryMode
from app.models.person import Gender as PersonGender
from app.models.person import Person, PersonStatus
from app.services.settings.bank_directory import OrgBankDirectoryService

DEFAULT_SHERPACKAGE_ORG_ID = uuid.UUID("00000000-0000-0000-0000-00000000d002")
SHERPACKAGE_EMAIL_DOMAIN = "sherpackageonline.com"

SHERPACKAGE_EMPLOYEES = [
    {
        "code": "SHP-0001",
        "first_name": "Amara",
        "last_name": "Nwankwo",
        "designation": "CEO",
        "department": "EXEC",
        "grade": "L4",
        "location": "HQ-LAG",
        "gender": EmployeeGender.FEMALE,
    },
    {
        "code": "SHP-0002",
        "first_name": "Tobi",
        "last_name": "Adewale",
        "designation": "LEAD-ENG",
        "department": "ENG",
        "grade": "L3",
        "location": "HQ-LAG",
        "gender": EmployeeGender.MALE,
    },
    {
        "code": "SHP-0003",
        "first_name": "Fatima",
        "last_name": "Yusuf",
        "designation": "PM",
        "department": "PROD",
        "grade": "L3",
        "location": "HQ-LAG",
        "gender": EmployeeGender.FEMALE,
    },
    {
        "code": "SHP-0004",
        "first_name": "Chinedu",
        "last_name": "Okoro",
        "designation": "DEVOPS",
        "department": "OPS",
        "grade": "L2",
        "location": "REMOTE",
        "gender": EmployeeGender.MALE,
    },
    {
        "code": "SHP-0005",
        "first_name": "Miriam",
        "last_name": "Eze",
        "designation": "PEOPLE-FIN",
        "department": "FINHR",
        "grade": "L2",
        "location": "HQ-LAG",
        "gender": EmployeeGender.FEMALE,
    },
]


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "admin")


def _sherpackage_org_id() -> uuid.UUID:
    return uuid.UUID(
        os.getenv("SHERPACKAGE_ORGANIZATION_ID", str(DEFAULT_SHERPACKAGE_ORG_ID))
    )


def _work_email(first_name: str, last_name: str) -> str:
    domain = os.getenv("SHERPACKAGE_WORK_EMAIL_DOMAIN", SHERPACKAGE_EMAIL_DOMAIN)
    return f"{first_name.lower()}.{last_name.lower()}@{domain.lstrip('@')}"


def _ensure_sherpackage_org() -> uuid.UUID:
    org_id = _sherpackage_org_id()
    with cross_org_session() as db:
        org = db.get(Organization, org_id)
        if org is None:
            org = db.scalar(
                select(Organization).where(Organization.organization_code == "SHP")
            )
            if org is not None:
                org_id = org.organization_id
        if org is None:
            org = Organization(
                organization_id=org_id,
                organization_code="SHP",
                slug="sherpackage",
                legal_name="Sherpackage Technologies Limited",
                trading_name="Sherpackage",
                registration_number="RC-SHERPACKAGE-001",
                tax_identification_number="TIN-SHERPACKAGE-001",
                incorporation_date=date(2024, 2, 1),
                jurisdiction_country_code="NG",
                functional_currency_code="NGN",
                presentation_currency_code="NGN",
                fiscal_year_end_month=12,
                fiscal_year_end_day=31,
                sector_type=SectorType.PRIVATE,
                accounting_framework=AccountingFramework.IFRS,
                fund_accounting_enabled=False,
                commitment_control_enabled=False,
                pms_ohcsf_enabled=False,
                performance_mode=PerformanceMode.PRIVATE,
                timezone="Africa/Lagos",
                date_format="DD/MM/YYYY",
                number_format="1,234.56",
                contact_email=f"hello@{SHERPACKAGE_EMAIL_DOMAIN}",
                contact_phone="+234 700 743 7722",
                address_line1="18 Product Studio Lane",
                city="Lagos",
                state="Lagos",
                postal_code="100001",
                country="Nigeria",
                website_url="https://sherpackageonline.com",
                hr_employee_id_prefix="SHP",
                hr_employee_id_format="SHP-{SEQ}",
                hr_payroll_frequency="MONTHLY",
                hr_leave_year_start_month=1,
                hr_probation_days=90,
                hr_attendance_mode="HYBRID",
                is_active=True,
            )
            db.add(org)
        else:
            org_id = org.organization_id
            org.legal_name = "Sherpackage Technologies Limited"
            org.trading_name = "Sherpackage"
            org.slug = org.slug or "sherpackage"
            org.functional_currency_code = org.functional_currency_code or "NGN"
            org.presentation_currency_code = org.presentation_currency_code or "NGN"
            org.contact_email = f"hello@{SHERPACKAGE_EMAIL_DOMAIN}"
            org.website_url = "https://sherpackageonline.com"
            org.hr_employee_id_prefix = "SHP"
            org.hr_employee_id_format = "SHP-{SEQ}"
            org.is_active = True
        db.commit()
    return org_id


def _attach_admin_to_sherpackage_org(org_id: uuid.UUID) -> None:
    if not _env_bool("SHERPACKAGE_ATTACH_ADMIN_TO_ORG", True):
        return
    with cross_org_session() as db:
        credential = db.scalar(
            select(UserCredential).where(
                UserCredential.provider == AuthProvider.local,
                UserCredential.username == _admin_username(),
            )
        )
        person = db.get(Person, credential.person_id) if credential else None
        if person is None:
            return
        person.organization_id = org_id
        person.is_active = True
        person.status = PersonStatus.active
        db.commit()


def _get_or_create_by_code(db, model_cls, code_field: str, code: str, **values):
    instance = db.scalar(
        select(model_cls).where(
            model_cls.organization_id == db.info["organization_id"],
            getattr(model_cls, code_field) == code,
        )
    )
    if instance is None:
        instance = model_cls(
            organization_id=db.info["organization_id"],
            **{code_field: code},
            **values,
        )
        db.add(instance)
        db.flush()
    else:
        for key, value in values.items():
            setattr(instance, key, value)
    return instance


def _seed_locations(db) -> dict[str, Location]:
    rows = [
        (
            "HQ-LAG",
            {
                "location_name": "Sherpackage Lagos Studio",
                "location_type": LocationType.HEAD_OFFICE,
                "address_line_1": "18 Product Studio Lane",
                "city": "Lagos",
                "state_province": "Lagos",
                "country_code": "NG",
                "latitude": Decimal("6.524400"),
                "longitude": Decimal("3.379200"),
                "geofence_radius_m": 400,
                "geofence_enabled": True,
                "is_active": True,
            },
        ),
        (
            "REMOTE",
            {
                "location_name": "Remote Delivery Team",
                "location_type": LocationType.REMOTE,
                "city": "Remote",
                "country_code": "NG",
                "geofence_enabled": False,
                "is_active": True,
            },
        ),
    ]
    return {
        code: _get_or_create_by_code(db, Location, "location_code", code, **values)
        for code, values in rows
    }


def _seed_departments(db) -> dict[str, Department]:
    rows = [
        ("EXEC", "Executive Office", "Company strategy, partnerships, and governance."),
        ("ENG", "Software Engineering", "Product engineering and platform delivery."),
        ("PROD", "Product & Design", "Product management, UX, and customer discovery."),
        ("OPS", "Cloud Operations", "Infrastructure, DevOps, and release operations."),
        ("FINHR", "People & Finance", "People operations, finance, and administration."),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            Department,
            "department_code",
            code,
            department_name=name,
            description=description,
            is_active=True,
        )
        for code, name, description in rows
    }


def _seed_designations(db) -> dict[str, Designation]:
    rows = [
        ("CEO", "Chief Executive Officer"),
        ("LEAD-ENG", "Lead Software Engineer"),
        ("SWE", "Software Engineer"),
        ("QA", "Quality Assurance Engineer"),
        ("DEVOPS", "DevOps Engineer"),
        ("PM", "Product Manager"),
        ("UX", "Product Designer"),
        ("PEOPLE-FIN", "People & Finance Officer"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            Designation,
            "designation_code",
            code,
            designation_name=name,
            description=f"Sherpackage {name} role.",
            is_active=True,
        )
        for code, name in rows
    }


def _seed_employment_types(db) -> dict[str, EmploymentType]:
    rows = [
        ("FT", "Full-time"),
        ("CT", "Contract"),
        ("PT", "Part-time"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            EmploymentType,
            "type_code",
            code,
            type_name=name,
            description=f"Sherpackage {name.lower()} employment arrangement.",
            is_active=True,
        )
        for code, name in rows
    }


def _seed_grades(db) -> dict[str, EmployeeGrade]:
    rows = [
        ("L1", "Associate", 1, "1800000", "3600000"),
        ("L2", "Specialist", 2, "3600000", "7200000"),
        ("L3", "Lead", 3, "7200000", "14400000"),
        ("L4", "Executive", 4, "14400000", "30000000"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            EmployeeGrade,
            "grade_code",
            code,
            grade_name=name,
            rank=rank,
            min_salary=Decimal(min_salary),
            max_salary=Decimal(max_salary),
            is_active=True,
        )
        for code, name, rank, min_salary, max_salary in rows
    }


def _seed_shifts(db) -> dict[str, ShiftType]:
    rows = [
        ("CORE", "Core Workday", time(9, 0), time(17, 0), "8.00"),
        ("FLEX", "Flexible Engineering", time(10, 0), time(18, 0), "8.00"),
        ("OPS", "Release Operations", time(8, 0), time(16, 0), "8.00"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            ShiftType,
            "shift_code",
            code,
            shift_name=name,
            start_time=start,
            end_time=end,
            working_hours=Decimal(hours),
            late_entry_grace_period=15,
            early_exit_grace_period=10,
            enable_half_day=True,
            half_day_threshold_hours=Decimal("4.00"),
            enable_overtime=True,
            overtime_threshold_hours=Decimal("9.00"),
            break_duration_minutes=60,
            description=f"Sherpackage {name.lower()} schedule.",
            is_active=True,
        )
        for code, name, start, end, hours in rows
    }


def _ensure_person(db, *, first_name: str, last_name: str, email: str, phone: str):
    person = db.scalar(select(Person).where(Person.email == email))
    if person is None:
        person = Person(
            organization_id=db.info["organization_id"],
            first_name=first_name,
            last_name=last_name,
            display_name=f"{first_name} {last_name}",
            email=email,
            email_verified=True,
            phone=phone,
            gender=PersonGender.unknown,
            status=PersonStatus.active,
            is_active=True,
            city="Lagos",
            region="Lagos",
            country_code="NG",
            timezone="Africa/Lagos",
        )
        db.add(person)
        db.flush()
    else:
        person.organization_id = db.info["organization_id"]
        person.first_name = first_name
        person.last_name = last_name
        person.display_name = f"{first_name} {last_name}"
        person.email_verified = True
        person.phone = phone
        person.status = PersonStatus.active
        person.is_active = True
    return person


def _seed_employees(
    db,
    *,
    departments: dict[str, Department],
    designations: dict[str, Designation],
    employment_types: dict[str, EmploymentType],
    grades: dict[str, EmployeeGrade],
    locations: dict[str, Location],
    shifts: dict[str, ShiftType],
) -> dict[str, Employee]:
    employees: dict[str, Employee] = {}
    for idx, row in enumerate(SHERPACKAGE_EMPLOYEES, start=1):
        email = _work_email(row["first_name"], row["last_name"])
        person = _ensure_person(
            db,
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=email,
            phone=f"+234 801 743 {idx:04d}",
        )
        employee = db.scalar(
            select(Employee).where(
                Employee.organization_id == db.info["organization_id"],
                Employee.employee_code == row["code"],
            )
        )
        if employee is None:
            employee = Employee(
                organization_id=db.info["organization_id"],
                person_id=person.id,
                employee_code=row["code"],
                date_of_joining=date(2025, idx, 3),
                status=EmployeeStatus.ACTIVE,
            )
            db.add(employee)
            db.flush()
        employee.person_id = person.id
        employee.department_id = departments[row["department"]].department_id
        employee.designation_id = designations[row["designation"]].designation_id
        employee.employment_type_id = employment_types["FT"].employment_type_id
        employee.grade_id = grades[row["grade"]].grade_id
        employee.assigned_location_id = locations[row["location"]].location_id
        employee.default_shift_type_id = shifts[
            "OPS" if row["department"] == "OPS" else "FLEX"
        ].shift_type_id
        employee.gender = row["gender"]
        employee.personal_email = email.replace(
            f"@{SHERPACKAGE_EMAIL_DOMAIN}", "@example.com"
        )
        employee.personal_phone = person.phone
        employee.ctc = grades[row["grade"]].min_salary
        employee.salary_mode = SalaryMode.BANK
        employee.status = EmployeeStatus.ACTIVE
        employees[row["code"]] = employee

    db.flush()
    employees["SHP-0002"].reports_to_id = employees["SHP-0001"].employee_id
    employees["SHP-0003"].reports_to_id = employees["SHP-0001"].employee_id
    employees["SHP-0004"].reports_to_id = employees["SHP-0002"].employee_id
    employees["SHP-0005"].reports_to_id = employees["SHP-0001"].employee_id

    departments["EXEC"].head_id = employees["SHP-0001"].employee_id
    departments["ENG"].head_id = employees["SHP-0002"].employee_id
    departments["PROD"].head_id = employees["SHP-0003"].employee_id
    departments["OPS"].head_id = employees["SHP-0004"].employee_id
    departments["FINHR"].head_id = employees["SHP-0005"].employee_id
    return employees


def main() -> None:
    if not _env_bool("SEED_SHERPACKAGE_ON_START", True):
        print("Sherpackage seed disabled.")
        return

    org_id = _ensure_sherpackage_org()
    _attach_admin_to_sherpackage_org(org_id)
    with session_for_org(org_id) as db:
        locations = _seed_locations(db)
        departments = _seed_departments(db)
        designations = _seed_designations(db)
        employment_types = _seed_employment_types(db)
        grades = _seed_grades(db)
        shifts = _seed_shifts(db)
        employees = _seed_employees(
            db,
            departments=departments,
            designations=designations,
            employment_types=employment_types,
            grades=grades,
            locations=locations,
            shifts=shifts,
        )
        bank_count = OrgBankDirectoryService(db).seed_defaults(org_id)
        db.commit()

    print("Sherpackage organization ready")
    print(f"  Organization: Sherpackage Technologies Limited ({org_id})")
    print(f"  Work email domain: @{SHERPACKAGE_EMAIL_DOMAIN}")
    print(f"  Locations: {len(locations)}")
    print(f"  Departments: {len(departments)}")
    print(f"  Designations: {len(designations)}")
    print(f"  Shifts: {len(shifts)}")
    print(f"  Employees: {len(employees)}")
    print(f"  Banks seeded: {bank_count}")


if __name__ == "__main__":
    main()
