"""People assets depreciation service."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fixed_assets.depreciation_run import DepreciationRun, DepreciationRunStatus
from app.models.fixed_assets.depreciation_schedule import DepreciationSchedule
from app.services.fixed_assets.depreciation import depreciation_service

__all__ = ["PeopleAssetDepreciationService"]


class PeopleAssetDepreciationService:
    """Expose fixed asset depreciation workflow through people/assets module."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def run_depreciation(
        self,
        org_id: UUID,
        *,
        fiscal_period_id: UUID,
        run_by_user_id: UUID,
        description: str | None = None,
    ) -> DepreciationRun:
        run = depreciation_service.create_depreciation_run(
            db=self.db,
            organization_id=org_id,
            fiscal_period_id=fiscal_period_id,
            created_by_user_id=run_by_user_id,
            description=description,
        )
        return depreciation_service.calculate_run(
            db=self.db,
            organization_id=org_id,
            run_id=run.run_id,
        )

    def calculate_run(self, org_id: UUID, run_id: UUID) -> DepreciationRun:
        return depreciation_service.calculate_run(
            db=self.db,
            organization_id=org_id,
            run_id=run_id,
        )

    def list_runs(
        self,
        org_id: UUID,
        *,
        fiscal_period_id: UUID | None = None,
        status: DepreciationRunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DepreciationRun]:
        return depreciation_service.list(
            db=self.db,
            organization_id=str(org_id),
            fiscal_period_id=str(fiscal_period_id) if fiscal_period_id else None,
            status=status,
            limit=limit,
            offset=offset,
        )

    def post_run(
        self,
        org_id: UUID,
        run_id: UUID,
        *,
        posted_by_user_id: UUID,
        posting_date: date | None = None,
    ) -> DepreciationRun:
        return depreciation_service.post_run(
            db=self.db,
            organization_id=org_id,
            run_id=run_id,
            posted_by_user_id=posted_by_user_id,
            posting_date=posting_date,
        )

    def list_run_schedules(
        self,
        org_id: UUID,
        run_id: UUID,
    ) -> list[DepreciationSchedule]:
        return depreciation_service.get_run_schedules(
            db=self.db,
            organization_id=org_id,
            run_id=run_id,
        )
