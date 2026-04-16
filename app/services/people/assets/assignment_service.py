"""Asset assignment service."""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fixed_assets.asset import Asset, AssetStatus
from app.models.people.assets.assignment import (
    AssetAssignment,
    AssetAssignmentMovement,
    AssetCondition,
    AssignmentMovementType,
    AssignmentStatus,
)
from app.models.people.hr.employee import Employee
from app.services.people.assets.lifecycle_event_service import record_asset_lifecycle_event
from app.services.common import (
    ConflictError,
    NotFoundError,
    PaginatedResult,
    PaginationParams,
    ValidationError,
)

logger = logging.getLogger(__name__)

__all__ = ["AssetAssignmentService"]


class AssetAssignmentService:
    """Manage asset assignments to employees."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_asset(self, org_id: UUID, asset_id: UUID) -> Asset:
        asset = self.db.get(Asset, asset_id)
        if not asset or asset.organization_id != org_id:
            raise NotFoundError("Asset not found")
        return asset

    def _get_employee(self, org_id: UUID, employee_id: UUID) -> Employee:
        employee = self.db.get(Employee, employee_id)
        if not employee or employee.organization_id != org_id:
            raise NotFoundError("Employee not found")
        return employee

    def _sync_finance_asset_on_issue(
        self,
        asset: Asset,
        employee: Employee,
        issued_on: date,
        location_id: UUID | None = None,
    ) -> None:
        if asset.status in {AssetStatus.DISPOSED, AssetStatus.IMPAIRED}:
            raise ValidationError(f"Cannot assign asset in {asset.status.value} status")
        if asset.status == AssetStatus.DRAFT:
            asset.status = AssetStatus.ACTIVE
            asset.in_service_date = asset.in_service_date or issued_on
            asset.depreciation_start_date = (
                asset.depreciation_start_date or asset.in_service_date
            )
        asset.custodian_employee_id = employee.employee_id
        if location_id is not None:
            asset.location_id = location_id

    def _log_movement(
        self,
        org_id: UUID,
        *,
        asset_id: UUID,
        movement_type: AssignmentMovementType,
        moved_on: date,
        assignment_id: UUID | None = None,
        from_employee_id: UUID | None = None,
        to_employee_id: UUID | None = None,
        from_location_id: UUID | None = None,
        to_location_id: UUID | None = None,
        notes: str | None = None,
        moved_by_user_id: UUID | None = None,
    ) -> AssetAssignmentMovement:
        movement = AssetAssignmentMovement(
            organization_id=org_id,
            asset_id=asset_id,
            assignment_id=assignment_id,
            movement_type=movement_type,
            from_employee_id=from_employee_id,
            to_employee_id=to_employee_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            moved_on=moved_on,
            notes=notes,
            moved_by_user_id=moved_by_user_id,
        )
        self.db.add(movement)
        return movement

    def list_assignments(
        self,
        org_id: UUID,
        *,
        asset_id: UUID | None = None,
        employee_id: UUID | None = None,
        status: AssignmentStatus | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[AssetAssignment]:
        query = select(AssetAssignment).where(AssetAssignment.organization_id == org_id)

        if asset_id:
            query = query.where(AssetAssignment.asset_id == asset_id)

        if employee_id:
            query = query.where(AssetAssignment.employee_id == employee_id)

        if status:
            query = query.where(AssetAssignment.status == status)

        query = query.order_by(AssetAssignment.issued_on.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)

        items = list(self.db.scalars(query).all())

        return PaginatedResult(
            items=items,
            total=total,
            offset=pagination.offset if pagination else 0,
            limit=pagination.limit if pagination else len(items),
        )

    def list_assignment_movements(
        self,
        org_id: UUID,
        *,
        asset_id: UUID | None = None,
        employee_id: UUID | None = None,
        movement_type: AssignmentMovementType | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[AssetAssignmentMovement]:
        query = select(AssetAssignmentMovement).where(
            AssetAssignmentMovement.organization_id == org_id
        )
        if asset_id:
            query = query.where(AssetAssignmentMovement.asset_id == asset_id)
        if employee_id:
            query = query.where(
                (AssetAssignmentMovement.from_employee_id == employee_id)
                | (AssetAssignmentMovement.to_employee_id == employee_id)
            )
        if movement_type:
            query = query.where(AssetAssignmentMovement.movement_type == movement_type)
        query = query.order_by(
            AssetAssignmentMovement.moved_on.desc(),
            AssetAssignmentMovement.created_at.desc(),
        )
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)
        items = list(self.db.scalars(query).all())
        return PaginatedResult(
            items=items,
            total=total,
            offset=pagination.offset if pagination else 0,
            limit=pagination.limit if pagination else len(items),
        )

    def list_available_assets(
        self,
        org_id: UUID,
        *,
        location_id: UUID | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[Asset]:
        active_assignment_subq = (
            select(AssetAssignment.asset_id)
            .where(
                AssetAssignment.organization_id == org_id,
                AssetAssignment.status == AssignmentStatus.ISSUED,
            )
            .subquery()
        )
        query = select(Asset).where(
            Asset.organization_id == org_id,
            Asset.status.notin_([AssetStatus.DISPOSED, AssetStatus.IMPAIRED]),
            ~Asset.asset_id.in_(select(active_assignment_subq.c.asset_id)),
        )
        if location_id:
            query = query.where(Asset.location_id == location_id)
        query = query.order_by(Asset.asset_name.asc())
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)
        items = list(self.db.scalars(query).all())
        return PaginatedResult(
            items=items,
            total=total,
            offset=pagination.offset if pagination else 0,
            limit=pagination.limit if pagination else len(items),
        )

    def get_assignment(self, org_id: UUID, assignment_id: UUID) -> AssetAssignment:
        assignment = self.db.scalar(
            select(AssetAssignment).where(
                AssetAssignment.organization_id == org_id,
                AssetAssignment.assignment_id == assignment_id,
            )
        )
        if not assignment:
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return assignment

    def issue_asset(
        self,
        org_id: UUID,
        *,
        asset_id: UUID,
        employee_id: UUID,
        issued_on: date,
        expected_return_date: date | None = None,
        condition_on_issue: AssetCondition | None = None,
        notes: str | None = None,
        location_id: UUID | None = None,
        moved_by_user_id: UUID | None = None,
    ) -> AssetAssignment:
        asset = self._get_asset(org_id, asset_id)
        prev_status = asset.status
        prev_owner_id = asset.custodian_employee_id
        employee = self._get_employee(org_id, employee_id)
        prev_location_id = asset.location_id

        existing = self.db.scalar(
            select(AssetAssignment).where(
                AssetAssignment.organization_id == org_id,
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.status == AssignmentStatus.ISSUED,
            )
        )
        if existing:
            raise ConflictError("Asset is already assigned")

        self._sync_finance_asset_on_issue(asset, employee, issued_on, location_id)

        assignment = AssetAssignment(
            organization_id=org_id,
            asset_id=asset_id,
            employee_id=employee_id,
            issued_on=issued_on,
            expected_return_date=expected_return_date,
            condition_on_issue=condition_on_issue,
            status=AssignmentStatus.ISSUED,
            notes=notes,
        )
        self.db.add(assignment)
        self.db.flush()
        record_asset_lifecycle_event(
            self.db,
            org_id=org_id,
            asset_id=asset.asset_id,
            event_category="OWNERSHIP",
            event_type="ASSIGNED",
            source_type="asset_assignment",
            source_record_id=assignment.assignment_id,
            actor_user_id=moved_by_user_id,
            previous_owner_employee_id=prev_owner_id,
            new_owner_employee_id=employee.employee_id,
            notes=f"Asset assigned to employee {employee.employee_id}",
        )
        if prev_location_id != asset.location_id:
            record_asset_lifecycle_event(
                self.db,
                org_id=org_id,
                asset_id=asset.asset_id,
                event_category="LOCATION",
                event_type="LOCATION_CHANGED",
                source_type="asset_assignment",
                source_record_id=assignment.assignment_id,
                actor_user_id=moved_by_user_id,
                previous_location_id=prev_location_id,
                new_location_id=asset.location_id,
                notes="Asset location updated on issue",
            )
        if prev_status != asset.status:
            record_asset_lifecycle_event(
                self.db,
                org_id=org_id,
                asset_id=asset.asset_id,
                event_category="STATE",
                event_type="STATE_CHANGED",
                source_type="asset",
                source_record_id=asset.asset_id,
                actor_user_id=moved_by_user_id,
                previous_status=prev_status.value,
                new_status=asset.status.value,
                notes="Asset state changed during issue",
            )
        self._log_movement(
            org_id,
            asset_id=asset.asset_id,
            assignment_id=assignment.assignment_id,
            movement_type=AssignmentMovementType.ASSIGNED,
            from_employee_id=None,
            to_employee_id=employee.employee_id,
            from_location_id=prev_location_id,
            to_location_id=asset.location_id,
            moved_on=issued_on,
            notes=notes,
            moved_by_user_id=moved_by_user_id,
        )
        self.db.flush()
        return assignment

    def return_asset(
        self,
        org_id: UUID,
        assignment_id: UUID,
        *,
        returned_on: date | None = None,
        condition_on_return: AssetCondition | None = None,
        notes: str | None = None,
        moved_by_user_id: UUID | None = None,
    ) -> AssetAssignment:
        assignment = self.get_assignment(org_id, assignment_id)
        if assignment.status != AssignmentStatus.ISSUED:
            raise ValidationError(
                f"Cannot return assignment in {assignment.status.value} status"
            )
        asset = self._get_asset(org_id, assignment.asset_id)
        prev_owner_id = asset.custodian_employee_id
        assignment.status = AssignmentStatus.RETURNED
        assignment.returned_on = returned_on or date.today()
        assignment.condition_on_return = condition_on_return
        if notes:
            assignment.notes = notes
        asset.custodian_employee_id = None
        record_asset_lifecycle_event(
            self.db,
            org_id=org_id,
            asset_id=asset.asset_id,
            event_category="OWNERSHIP",
            event_type="RETURNED",
            source_type="asset_assignment",
            source_record_id=assignment.assignment_id,
            actor_user_id=moved_by_user_id,
            previous_owner_employee_id=prev_owner_id,
            new_owner_employee_id=None,
            notes="Asset returned by employee",
        )
        self._log_movement(
            org_id,
            asset_id=asset.asset_id,
            assignment_id=assignment.assignment_id,
            movement_type=AssignmentMovementType.RETURNED,
            from_employee_id=assignment.employee_id,
            to_employee_id=None,
            from_location_id=asset.location_id,
            to_location_id=asset.location_id,
            moved_on=assignment.returned_on,
            notes=notes,
            moved_by_user_id=moved_by_user_id,
        )
        self.db.flush()
        return assignment

    def transfer_asset(
        self,
        org_id: UUID,
        assignment_id: UUID,
        *,
        new_employee_id: UUID,
        issued_on: date | None = None,
        expected_return_date: date | None = None,
        condition_on_issue: AssetCondition | None = None,
        notes: str | None = None,
        new_location_id: UUID | None = None,
        moved_by_user_id: UUID | None = None,
        movement_type: AssignmentMovementType = AssignmentMovementType.TRANSFERRED,
    ) -> AssetAssignment:
        assignment = self.get_assignment(org_id, assignment_id)
        if assignment.status != AssignmentStatus.ISSUED:
            raise ValidationError(
                f"Cannot transfer assignment in {assignment.status.value} status"
            )
        asset = self._get_asset(org_id, assignment.asset_id)
        from_employee_id = assignment.employee_id
        from_location_id = asset.location_id
        new_employee = self._get_employee(org_id, new_employee_id)
        prev_owner_id = assignment.employee_id
        assignment.status = AssignmentStatus.TRANSFERRED
        self.db.flush()

        self._sync_finance_asset_on_issue(
            asset,
            new_employee,
            issued_on or date.today(),
            new_location_id,
        )

        new_assignment = AssetAssignment(
            organization_id=org_id,
            asset_id=assignment.asset_id,
            employee_id=new_employee_id,
            issued_on=issued_on or date.today(),
            expected_return_date=expected_return_date,
            condition_on_issue=condition_on_issue or assignment.condition_on_issue,
            status=AssignmentStatus.ISSUED,
            notes=notes,
            transfer_from_assignment_id=assignment.assignment_id,
        )
        self.db.add(new_assignment)
        self.db.flush()
        record_asset_lifecycle_event(
            self.db,
            org_id=org_id,
            asset_id=asset.asset_id,
            event_category="OWNERSHIP",
            event_type="OWNERSHIP_TRANSFERRED",
            source_type="asset_assignment",
            source_record_id=new_assignment.assignment_id,
            actor_user_id=moved_by_user_id,
            previous_owner_employee_id=prev_owner_id,
            new_owner_employee_id=new_employee_id,
            notes=f"Ownership transferred from {from_employee_id} to {new_employee_id}",
        )
        if from_location_id != asset.location_id:
            record_asset_lifecycle_event(
                self.db,
                org_id=org_id,
                asset_id=asset.asset_id,
                event_category="LOCATION",
                event_type="LOCATION_CHANGED",
                source_type="asset_assignment",
                source_record_id=new_assignment.assignment_id,
                actor_user_id=moved_by_user_id,
                previous_location_id=from_location_id,
                new_location_id=asset.location_id,
                notes="Asset location updated during transfer",
            )
        self._log_movement(
            org_id,
            asset_id=asset.asset_id,
            assignment_id=new_assignment.assignment_id,
            movement_type=movement_type,
            from_employee_id=from_employee_id,
            to_employee_id=new_employee.employee_id,
            from_location_id=from_location_id,
            to_location_id=asset.location_id,
            moved_on=issued_on or date.today(),
            notes=notes,
            moved_by_user_id=moved_by_user_id,
        )
        self.db.flush()
        return new_assignment

    def reassign_asset(
        self,
        org_id: UUID,
        assignment_id: UUID,
        *,
        new_employee_id: UUID,
        issued_on: date | None = None,
        expected_return_date: date | None = None,
        condition_on_issue: AssetCondition | None = None,
        notes: str | None = None,
        new_location_id: UUID | None = None,
        moved_by_user_id: UUID | None = None,
    ) -> AssetAssignment:
        return self.transfer_asset(
            org_id=org_id,
            assignment_id=assignment_id,
            new_employee_id=new_employee_id,
            issued_on=issued_on,
            expected_return_date=expected_return_date,
            condition_on_issue=condition_on_issue,
            notes=notes,
            new_location_id=new_location_id,
            moved_by_user_id=moved_by_user_id,
            movement_type=AssignmentMovementType.REASSIGNED,
        )

    def move_asset_location(
        self,
        org_id: UUID,
        *,
        asset_id: UUID,
        new_location_id: UUID,
        moved_on: date | None = None,
        notes: str | None = None,
        moved_by_user_id: UUID | None = None,
    ) -> Asset:
        asset = self._get_asset(org_id, asset_id)
        old_location_id = asset.location_id
        if old_location_id == new_location_id:
            return asset
        active_assignment = self.db.scalar(
            select(AssetAssignment).where(
                AssetAssignment.organization_id == org_id,
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.status == AssignmentStatus.ISSUED,
            )
        )
        from_employee_id = active_assignment.employee_id if active_assignment else None
        asset.location_id = new_location_id
        self._log_movement(
            org_id,
            asset_id=asset.asset_id,
            assignment_id=active_assignment.assignment_id if active_assignment else None,
            movement_type=AssignmentMovementType.LOCATION_TRANSFERRED,
            from_employee_id=from_employee_id,
            to_employee_id=from_employee_id,
            from_location_id=old_location_id,
            to_location_id=new_location_id,
            moved_on=moved_on or date.today(),
            notes=notes,
            moved_by_user_id=moved_by_user_id,
        )
        record_asset_lifecycle_event(
            self.db,
            org_id=org_id,
            asset_id=asset.asset_id,
            event_category="LOCATION",
            event_type="LOCATION_CHANGED",
            source_type="asset",
            source_record_id=asset.asset_id,
            actor_user_id=moved_by_user_id,
            previous_location_id=old_location_id,
            new_location_id=new_location_id,
            notes=notes or "Asset moved to new location",
        )
        self.db.flush()
        return asset
