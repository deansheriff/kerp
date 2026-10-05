#!/usr/bin/env python3
"""Publish Sherpackage's prepared hiring package once during container startup."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session_context import cross_org_session, session_for_org
from app.models.domain_settings import (
    DomainSetting,
    SettingDomain,
    SettingScope,
    SettingValueType,
)
from app.models.finance.core_org.organization import Organization
from scripts.seed_sherpackage_digital_marketer import JOB_CODE, seed_job_package

SEED_KEY = "seed_sherpackage_digital_marketer_v1"


def seed_once(db: Session, org_id: UUID) -> dict[str, int] | None:
    """Flush the package and completion marker together; caller commits once."""
    if db.info.get("organization_id") != org_id or db.info.get("allow_cross_org"):
        raise ValueError("A matching tenant-scoped session is required")
    # Same transaction lock as the manual seed, acquired before checking the marker.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(73421, org_id.int % (2**31))))
    marker = db.scalar(
        select(DomainSetting).where(
            DomainSetting.organization_id == org_id,
            DomainSetting.domain == SettingDomain.operations,
            DomainSetting.key == SEED_KEY,
        )
    )
    if marker is not None:
        return None

    opening, counts = seed_job_package(db, org_id, publish=True)
    db.add(
        DomainSetting(
            organization_id=org_id,
            scope=SettingScope.ORG_SPECIFIC,
            domain=SettingDomain.operations,
            key=SEED_KEY,
            value_type=SettingValueType.json,
            value_text=None,
            value_json={
                "job_code": JOB_CODE,
                "job_opening_id": str(opening.job_opening_id),
                "status": opening.status.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
    db.flush()
    return counts


def main() -> None:
    # Discover only the requested organization, then use the normal tenant session.
    with cross_org_session() as db:
        org_id = db.scalar(
            select(Organization.organization_id).where(
                Organization.organization_code == "SHP",
                Organization.is_active.is_(True),
            )
        )
    if org_id is None:
        print(
            "Digital Marketer startup seed skipped: active Sherpackage organization not found."
        )
        return

    with session_for_org(org_id) as db:
        counts = seed_once(db, org_id)
        db.commit()
    if counts is None:
        print(f"Digital Marketer startup seed skipped: already completed ({JOB_CODE}).")
    else:
        print(f"Digital Marketer startup seed completed ({JOB_CODE}).")
        for name, count in counts.items():
            print(f"  {name}: {count}")
        if not counts:
            print("  Existing package preserved; completion recorded.")


if __name__ == "__main__":
    main()
