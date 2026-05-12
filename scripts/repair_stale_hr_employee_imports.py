#!/usr/bin/env python3
"""Repair stale ERPNext HR import metadata.

Dry-run by default. With --execute, this prepares missing live HR employees for
safe re-import from staging without touching expense claims. Existing claim
employee_id values are preserved by keeping staging.imported_employee_id.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db import SessionLocal
from app.models.people.hr.department import Department
from app.models.people.hr.designation import Designation
from app.models.people.hr.employee import Employee
from app.models.people.hr.employee_grade import EmployeeGrade
from app.models.people.hr.employment_type import EmploymentType
from app.models.sync import SyncEntity, SyncStatus
from app.models.sync.staging import (
    StagingDepartment,
    StagingDesignation,
    StagingEmployee,
    StagingEmployeeGrade,
    StagingEmploymentType,
    StagingStatus,
    StagingSyncBatch,
)


STALE_REASON = "Stale sync mapping: target HR row is missing"


REPAIR_SPECS = [
    {
        "doctype": "Department",
        "target_table": "hr.department",
        "target_model": Department,
        "target_pk": Department.department_id,
        "staging_model": StagingDepartment,
        "staging_imported_attr": "imported_department_id",
        "label_attr": "department_name",
        "code_attr": "department_code",
    },
    {
        "doctype": "Designation",
        "target_table": "hr.designation",
        "target_model": Designation,
        "target_pk": Designation.designation_id,
        "staging_model": StagingDesignation,
        "staging_imported_attr": "imported_designation_id",
        "label_attr": "designation_name",
        "code_attr": "designation_code",
    },
    {
        "doctype": "Employment Type",
        "target_table": "hr.employment_type",
        "target_model": EmploymentType,
        "target_pk": EmploymentType.employment_type_id,
        "staging_model": StagingEmploymentType,
        "staging_imported_attr": "imported_employment_type_id",
        "label_attr": "type_name",
        "code_attr": "type_code",
    },
    {
        "doctype": "Employee Grade",
        "target_table": "hr.employee_grade",
        "target_model": EmployeeGrade,
        "target_pk": EmployeeGrade.grade_id,
        "staging_model": StagingEmployeeGrade,
        "staging_imported_attr": "imported_grade_id",
        "label_attr": "grade_name",
        "code_attr": "grade_code",
    },
    {
        "doctype": "Employee",
        "target_table": "hr.employee",
        "target_model": Employee,
        "target_pk": Employee.employee_id,
        "staging_model": StagingEmployee,
        "staging_imported_attr": "imported_employee_id",
        "label_attr": "employee_name",
        "code_attr": "employee_code",
    },
]


def _stale_mappings(db, spec):
    staging_model = spec["staging_model"]
    target_pk = spec["target_pk"]
    rows = (
        db.execute(
            select(SyncEntity, staging_model)
            .outerjoin(
                spec["target_model"],
                target_pk == SyncEntity.target_id,
            )
            .outerjoin(
                staging_model,
                (staging_model.organization_id == SyncEntity.organization_id)
                & (staging_model.source_name == SyncEntity.source_name),
            )
            .where(
                SyncEntity.source_system == "erpnext",
                SyncEntity.source_doctype == spec["doctype"],
                SyncEntity.target_table == spec["target_table"],
                SyncEntity.target_id.is_not(None),
                target_pk.is_(None),
            )
            .order_by(staging_model.source_name.asc().nulls_last())
        )
        .unique()
        .all()
    )
    return rows


def run(*, execute: bool, limit: int) -> int:
    with SessionLocal() as db:
        rows_by_doctype = {
            spec["doctype"]: (spec, _stale_mappings(db, spec)) for spec in REPAIR_SPECS
        }
        all_rows = [
            (spec, sync_entity, staging)
            for spec, rows in rows_by_doctype.values()
            for sync_entity, staging in rows
        ]
        with_staging = [(spec, se, st) for spec, se, st in all_rows if st is not None]
        without_staging = [(spec, se, st) for spec, se, st in all_rows if st is None]

        batches: dict[object, int] = defaultdict(int)
        for _, _, staging in with_staging:
            batches[staging.batch_id] += 1

        print("Stale ERPNext HR sync mappings:", len(all_rows))
        print("With staging rows available:", len(with_staging))
        print("Without staging rows:", len(without_staging))
        print("Affected staging batches:", len(batches))
        print()
        for doctype, (_, rows) in rows_by_doctype.items():
            print(f"{doctype}: {len(rows)}")
        print()

        print("Sample:")
        for spec, sync_entity, staging in all_rows[:limit]:
            if staging:
                code = getattr(staging, spec["code_attr"], "")
                label = getattr(staging, spec["label_attr"], "")
                print(
                    f"  {spec['doctype']}: {code} {label} -> {sync_entity.target_id} "
                    f"status={staging.validation_status} imported_at={staging.imported_at}"
                )
            else:
                print(
                    f"  {spec['doctype']}: {sync_entity.source_name} -> "
                    f"{sync_entity.target_id} (no staging row)"
                )

        if not execute:
            print()
            print("Dry run only. Re-run with --execute to reset stale import metadata.")
            return 0

        reset_count = 0
        failed_mapping_count = 0
        reopened_batches = 0

        for spec, sync_entity, staging in all_rows:
            sync_entity.sync_status = SyncStatus.FAILED
            sync_entity.error_message = STALE_REASON
            failed_mapping_count += 1

            if not staging:
                continue

            staging.validation_status = StagingStatus.VALID
            staging.validation_errors = None
            staging.imported_at = None
            setattr(staging, spec["staging_imported_attr"], sync_entity.target_id)
            reset_count += 1

        for batch_id in batches:
            batch = db.get(StagingSyncBatch, batch_id)
            if batch and batch.status not in ("VALIDATED", "SYNCED"):
                batch.status = "VALIDATED"
                batch.notes = (
                    "Reopened by repair_stale_hr_employee_imports.py after stale "
                    "Employee sync mappings were detected."
                )
                reopened_batches += 1

        db.commit()

        print()
        print("Executed repair metadata reset.")
        print("Sync mappings marked FAILED:", failed_mapping_count)
        print("Staging rows reset for import:", reset_count)
        print("Batches reopened:", reopened_batches)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare stale ERPNext Employee imports for safe re-import."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply metadata reset. Without this flag, only reports what would change.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Number of sample rows to print.",
    )
    args = parser.parse_args()
    return run(execute=args.execute, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
