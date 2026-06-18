#!/usr/bin/env python3
"""Seed an idempotent demo technology company organization."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from app.db.session_context import cross_org_session, session_for_org
from app.models.finance.core_org.location import Location, LocationType
from app.models.finance.core_org.organization import (
    AccountingFramework,
    Organization,
    PerformanceMode,
    SectorType,
)
from app.models.fleet.enums import (
    AssignmentType,
    FuelType,
    OwnershipType,
    VehicleStatus,
    VehicleType,
)
from app.models.fleet.vehicle import Vehicle
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

DEFAULT_DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-00000000d001")


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _demo_org_id() -> uuid.UUID:
    return uuid.UUID(os.getenv("DEMO_ORGANIZATION_ID", str(DEFAULT_DEMO_ORG_ID)))


def _table_exists(db, table_name: str, schema: str | None = None) -> bool:
    return inspect(db.get_bind()).has_table(table_name, schema=schema)


def _ensure_demo_org() -> uuid.UUID:
    org_id = _demo_org_id()
    with cross_org_session() as db:
        org = db.get(Organization, org_id)
        if org is None:
            org = db.scalar(
                select(Organization).where(Organization.organization_code == "NEXA")
            )
            if org is not None:
                org_id = org.organization_id
        if org is None:
            org = Organization(
                organization_id=org_id,
                organization_code="NEXA",
                slug="nexacloud",
                legal_name="NexaCloud Technologies Ltd",
                trading_name="NexaCloud",
                registration_number="RC-DEMO-TECH-001",
                tax_identification_number="TIN-DEMO-NEXA",
                incorporation_date=date(2020, 3, 16),
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
                contact_email="hello@nexacloud.example",
                contact_phone="+234 700 639 2256",
                address_line1="12 Innovation Drive",
                city="Lagos",
                state="Lagos",
                postal_code="100001",
                country="Nigeria",
                website_url="https://nexacloud.example",
                hr_employee_id_prefix="NC",
                hr_employee_id_format="NC-{YYYY}-{SEQ}",
                hr_payroll_frequency="MONTHLY",
                hr_leave_year_start_month=1,
                hr_probation_days=90,
                hr_attendance_mode="GEOFENCED",
                is_active=True,
            )
            db.add(org)
        else:
            org_id = org.organization_id
            org.legal_name = "NexaCloud Technologies Ltd"
            org.trading_name = "NexaCloud"
            org.slug = org.slug or "nexacloud"
            org.is_active = True
        db.commit()
    return org_id


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
                "location_name": "Lagos Innovation HQ",
                "location_type": LocationType.HEAD_OFFICE,
                "address_line_1": "12 Innovation Drive",
                "city": "Lagos",
                "state_province": "Lagos",
                "country_code": "NG",
                "latitude": Decimal("6.455000"),
                "longitude": Decimal("3.395800"),
                "geofence_radius_m": 500,
                "geofence_enabled": True,
                "is_active": True,
            },
        ),
        (
            "BR-ABV",
            {
                "location_name": "Abuja Cloud Delivery Office",
                "location_type": LocationType.BRANCH,
                "address_line_1": "8 Founders Avenue",
                "city": "Abuja",
                "state_province": "FCT",
                "country_code": "NG",
                "latitude": Decimal("9.076500"),
                "longitude": Decimal("7.398600"),
                "geofence_radius_m": 450,
                "geofence_enabled": True,
                "is_active": True,
            },
        ),
        (
            "BR-PHC",
            {
                "location_name": "Port Harcourt Support Hub",
                "location_type": LocationType.BRANCH,
                "address_line_1": "4 Data Centre Road",
                "city": "Port Harcourt",
                "state_province": "Rivers",
                "country_code": "NG",
                "latitude": Decimal("4.815600"),
                "longitude": Decimal("7.049800"),
                "geofence_radius_m": 450,
                "geofence_enabled": True,
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
        ("ENG", "Engineering", "Builds NexaCloud products and platforms."),
        ("PROD", "Product", "Owns product strategy, design, and delivery."),
        ("SRE", "Cloud Operations", "Runs infrastructure and customer reliability."),
        ("SALES", "Sales", "Manages enterprise pipeline and customer growth."),
        ("FIN", "Finance", "Owns accounting, payroll, and commercial controls."),
        ("HR", "People Operations", "Owns hiring, culture, and employee experience."),
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
        ("CTO", "Chief Technology Officer"),
        ("ENG-MGR", "Engineering Manager"),
        ("SWE-SR", "Senior Software Engineer"),
        ("SRE", "Site Reliability Engineer"),
        ("PM", "Product Manager"),
        ("UX", "Product Designer"),
        ("SALES-LEAD", "Sales Lead"),
        ("FIN-MGR", "Finance Manager"),
        ("HRBP", "People Operations Partner"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            Designation,
            "designation_code",
            code,
            designation_name=name,
            description=f"Demo {name} role.",
            is_active=True,
        )
        for code, name in rows
    }


def _seed_employment_types(db) -> dict[str, EmploymentType]:
    rows = [
        ("FT", "Full-time"),
        ("CT", "Contract"),
        ("INT", "Internship"),
    ]
    return {
        code: _get_or_create_by_code(
            db,
            EmploymentType,
            "type_code",
            code,
            type_name=name,
            description=f"Demo {name.lower()} employment arrangement.",
            is_active=True,
        )
        for code, name in rows
    }


def _seed_grades(db) -> dict[str, EmployeeGrade]:
    rows = [
        ("L1", "Associate", 1, "1800000", "3600000"),
        ("L2", "Specialist", 2, "3600000", "7200000"),
        ("L3", "Senior", 3, "7200000", "14400000"),
        ("L4", "Lead", 4, "14400000", "24000000"),
        ("L5", "Executive", 5, "24000000", "48000000"),
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
        ("DAY", "Day Shift", time(9, 0), time(17, 0), "8.00"),
        ("FLEX", "Flexible Product Shift", time(10, 0), time(18, 0), "8.00"),
        ("OPS", "Cloud Operations Shift", time(8, 0), time(16, 0), "8.00"),
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
            description=f"Demo {name.lower()} schedule.",
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
    rows = [
        ("NC-0001", "Ada", "Okafor", "ada.okafor@nexacloud.example", "CEO", "HR", "L5", "HQ-LAG"),
        ("NC-0002", "Tunde", "Balogun", "tunde.balogun@nexacloud.example", "CTO", "ENG", "L5", "HQ-LAG"),
        ("NC-0003", "Zainab", "Musa", "zainab.musa@nexacloud.example", "ENG-MGR", "ENG", "L4", "HQ-LAG"),
        ("NC-0004", "Chinedu", "Nwosu", "chinedu.nwosu@nexacloud.example", "SWE-SR", "ENG", "L3", "HQ-LAG"),
        ("NC-0005", "Amaka", "Eze", "amaka.eze@nexacloud.example", "PM", "PROD", "L3", "BR-ABV"),
        ("NC-0006", "Musa", "Danladi", "musa.danladi@nexacloud.example", "SRE", "SRE", "L3", "BR-PHC"),
        ("NC-0007", "Ife", "Adeyemi", "ife.adeyemi@nexacloud.example", "UX", "PROD", "L2", "HQ-LAG"),
        ("NC-0008", "Bola", "Johnson", "bola.johnson@nexacloud.example", "SALES-LEAD", "SALES", "L4", "BR-ABV"),
        ("NC-0009", "Grace", "Ibrahim", "grace.ibrahim@nexacloud.example", "FIN-MGR", "FIN", "L4", "HQ-LAG"),
        ("NC-0010", "Kemi", "Afolayan", "kemi.afolayan@nexacloud.example", "HRBP", "HR", "L3", "HQ-LAG"),
    ]
    employees: dict[str, Employee] = {}
    for idx, (code, first, last, email, desig, dept, grade, location) in enumerate(rows, start=1):
        person = _ensure_person(
            db,
            first_name=first,
            last_name=last,
            email=email,
            phone=f"+234 800 100 {idx:04d}",
        )
        employee = db.scalar(
            select(Employee).where(
                Employee.organization_id == db.info["organization_id"],
                Employee.employee_code == code,
            )
        )
        if employee is None:
            employee = Employee(
                organization_id=db.info["organization_id"],
                person_id=person.id,
                employee_code=code,
                date_of_joining=date(2024, min(idx, 12), 1),
                status=EmployeeStatus.ACTIVE,
            )
            db.add(employee)
            db.flush()
        employee.person_id = person.id
        employee.department_id = departments[dept].department_id
        employee.designation_id = designations[desig].designation_id
        employee.employment_type_id = employment_types["FT"].employment_type_id
        employee.grade_id = grades[grade].grade_id
        employee.assigned_location_id = locations[location].location_id
        employee.default_shift_type_id = shifts["OPS" if dept == "SRE" else "DAY"].shift_type_id
        employee.gender = EmployeeGender.FEMALE if first in {"Ada", "Zainab", "Amaka", "Ife", "Grace", "Kemi"} else EmployeeGender.MALE
        employee.personal_email = email.replace("@nexacloud.example", "@example.com")
        employee.personal_phone = person.phone
        employee.ctc = grades[grade].min_salary
        employee.salary_mode = SalaryMode.BANK
        employee.status = EmployeeStatus.ACTIVE
        employees[code] = employee

    db.flush()
    employees["NC-0003"].reports_to_id = employees["NC-0002"].employee_id
    for code in {"NC-0004", "NC-0006"}:
        employees[code].reports_to_id = employees["NC-0003"].employee_id
    for code in {"NC-0005", "NC-0007"}:
        employees[code].reports_to_id = employees["NC-0001"].employee_id
    departments["ENG"].head_id = employees["NC-0003"].employee_id
    departments["PROD"].head_id = employees["NC-0005"].employee_id
    departments["SRE"].head_id = employees["NC-0006"].employee_id
    departments["SALES"].head_id = employees["NC-0008"].employee_id
    departments["FIN"].head_id = employees["NC-0009"].employee_id
    departments["HR"].head_id = employees["NC-0010"].employee_id
    return employees


def _seed_fleet_if_available(db, locations: dict[str, Location], employees: dict[str, Employee]) -> int:
    if not _table_exists(db, "vehicle", schema="fleet"):
        return 0
    rows = [
        (
            "FLT-NC-001",
            {
                "registration_number": "LAG-NC-101",
                "make": "Toyota",
                "model": "Corolla Hybrid",
                "year": 2023,
                "vehicle_type": VehicleType.SEDAN,
                "fuel_type": FuelType.HYBRID,
                "ownership_type": OwnershipType.OWNED,
                "color": "Silver",
                "seating_capacity": 5,
                "current_odometer": 18450,
                "purchase_date": date(2024, 1, 10),
                "purchase_price": Decimal("18500000"),
                "license_expiry_date": date(2027, 1, 10),
                "location_id": locations["HQ-LAG"].location_id,
                "assignment_type": AssignmentType.POOL,
                "status": VehicleStatus.ACTIVE,
                "notes": "Demo pool vehicle for Lagos customer visits.",
            },
        ),
        (
            "FLT-NC-002",
            {
                "registration_number": "ABJ-NC-202",
                "make": "Hyundai",
                "model": "Tucson",
                "year": 2022,
                "vehicle_type": VehicleType.SUV,
                "fuel_type": FuelType.PETROL,
                "ownership_type": OwnershipType.OWNED,
                "color": "Blue",
                "seating_capacity": 5,
                "current_odometer": 32600,
                "purchase_date": date(2023, 11, 4),
                "purchase_price": Decimal("24000000"),
                "license_expiry_date": date(2026, 11, 4),
                "location_id": locations["BR-ABV"].location_id,
                "assigned_employee_id": employees["NC-0008"].employee_id,
                "assignment_type": AssignmentType.PERSONAL,
                "status": VehicleStatus.ACTIVE,
                "notes": "Demo vehicle assigned to Sales Lead.",
            },
        ),
    ]
    count = 0
    for code, values in rows:
        vehicle = _get_or_create_by_code(
            db,
            Vehicle,
            "vehicle_code",
            code,
            **values,
        )
        if vehicle:
            count += 1
    return count


def main() -> None:
    if not _env_bool("SEED_DEMO_ON_START", True):
        print("Demo seed disabled.")
        return

    org_id = _ensure_demo_org()
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
        fleet_count = _seed_fleet_if_available(db, locations, employees)
        db.commit()

    print("Demo organization ready")
    print(f"  Organization: NexaCloud Technologies Ltd ({org_id})")
    print(f"  Branches: {len(locations)}")
    print(f"  Departments: {len(departments)}")
    print(f"  Designations: {len(designations)}")
    print(f"  Shifts: {len(shifts)}")
    print(f"  Employees: {len(employees)}")
    print(f"  Vehicles: {fleet_count}")


if __name__ == "__main__":
    main()
