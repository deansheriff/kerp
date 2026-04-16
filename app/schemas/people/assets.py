"""
Asset assignment schemas.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.people.assets.assignment import AssetCondition, AssignmentStatus
from app.models.people.assets.assignment import AssignmentMovementType
from app.models.people.assets.tracking import AssetTrackingMethod
from app.models.people.assets.audit import (
    AssetAuditAdjustmentType,
    AssetAuditLineStatus,
    AssetAuditPlanStatus,
)
from app.models.fixed_assets.maintenance_request import (
    MaintenancePriority,
    MaintenanceRequestStatus,
)
from app.models.fixed_assets.maintenance_work_order import (
    MaintenanceWorkOrderPartStatus,
    MaintenanceWorkOrderStatus,
)


class AssetAssignmentBase(BaseModel):
    """Base asset assignment schema."""

    asset_id: UUID
    employee_id: UUID
    issued_on: date
    expected_return_date: date | None = None
    condition_on_issue: AssetCondition | None = None
    notes: str | None = None


class AssetAssignmentCreate(AssetAssignmentBase):
    """Create asset assignment request."""

    pass


class AssetAssignmentReturnRequest(BaseModel):
    """Return an asset assignment."""

    returned_on: date | None = None
    condition_on_return: AssetCondition | None = None
    notes: str | None = None


class AssetAssignmentTransferRequest(BaseModel):
    """Transfer an asset to another employee."""

    new_employee_id: UUID
    issued_on: date | None = None
    expected_return_date: date | None = None
    condition_on_issue: AssetCondition | None = None
    notes: str | None = None
    new_location_id: UUID | None = None


class AssetAssignmentReassignRequest(BaseModel):
    """Reassign an asset to a different employee/location."""

    new_employee_id: UUID
    issued_on: date | None = None
    expected_return_date: date | None = None
    condition_on_issue: AssetCondition | None = None
    notes: str | None = None
    new_location_id: UUID | None = None


class AssetLocationMoveRequest(BaseModel):
    """Move an asset between locations."""

    new_location_id: UUID
    moved_on: date | None = None
    notes: str | None = None


class AssetAssignmentRead(AssetAssignmentBase):
    """Asset assignment response."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: UUID
    organization_id: UUID
    returned_on: date | None = None
    status: AssignmentStatus
    condition_on_return: AssetCondition | None = None
    transfer_from_assignment_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetAssignmentListResponse(BaseModel):
    """Paginated asset assignment list response."""

    items: list[AssetAssignmentRead]
    total: int
    offset: int
    limit: int


class AssetAssignmentMovementRead(BaseModel):
    """Asset assignment movement event response."""

    model_config = ConfigDict(from_attributes=True)

    movement_id: UUID
    organization_id: UUID
    asset_id: UUID
    assignment_id: UUID | None = None
    movement_type: AssignmentMovementType
    from_employee_id: UUID | None = None
    to_employee_id: UUID | None = None
    from_location_id: UUID | None = None
    to_location_id: UUID | None = None
    moved_on: date
    notes: str | None = None
    moved_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetAvailableRead(BaseModel):
    """Available asset response for assignment queue."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    organization_id: UUID
    asset_number: str
    asset_name: str
    location_id: UUID | None = None
    status: str


class AssetTrackingEventCreate(BaseModel):
    """Record an asset tracking event."""

    asset_id: UUID
    tracking_method: AssetTrackingMethod
    tracked_at: datetime | None = None
    tracking_reference: str | None = None
    location_id: UUID | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    notes: str | None = None


class AssetTrackingEventRead(BaseModel):
    """Asset tracking event response."""

    model_config = ConfigDict(from_attributes=True)

    tracking_event_id: UUID
    organization_id: UUID
    asset_id: UUID
    tracking_method: AssetTrackingMethod
    tracking_reference: str | None = None
    tracked_at: datetime
    location_id: UUID | None = None
    previous_location_id: UUID | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    accuracy_meters: Decimal | None = None
    movement_logged: bool
    scanned_by_user_id: UUID | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetAuditPlanCreate(BaseModel):
    """Create asset audit plan."""

    title: str
    planned_date: date
    scope_location_id: UUID | None = None
    asset_ids: list[UUID] | None = None


class AssetAuditPlanRead(BaseModel):
    """Asset audit plan response."""

    model_config = ConfigDict(from_attributes=True)

    audit_plan_id: UUID
    organization_id: UUID
    plan_number: str
    title: str
    planned_date: date
    scope_location_id: UUID | None = None
    status: AssetAuditPlanStatus
    total_assets: int
    found_count: int
    missing_count: int
    discrepancy_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetAuditLineCheckRequest(BaseModel):
    """Physical check input for an audit line."""

    is_found: bool
    observed_location_id: UUID | None = None
    observed_custodian_employee_id: UUID | None = None
    observed_status: str | None = None
    discrepancy_notes: str | None = None


class AssetAuditLineRead(BaseModel):
    """Asset audit line response."""

    model_config = ConfigDict(from_attributes=True)

    audit_line_id: UUID
    organization_id: UUID
    audit_plan_id: UUID
    asset_id: UUID
    expected_location_id: UUID | None = None
    observed_location_id: UUID | None = None
    expected_custodian_employee_id: UUID | None = None
    observed_custodian_employee_id: UUID | None = None
    expected_status: str | None = None
    observed_status: str | None = None
    physical_check_at: datetime | None = None
    checked_by_user_id: UUID | None = None
    is_found: bool | None = None
    discrepancy_notes: str | None = None
    status: AssetAuditLineStatus
    created_at: datetime
    updated_at: datetime | None = None


class AssetAuditDiscrepancyRead(BaseModel):
    """Audit discrepancy response."""

    model_config = ConfigDict(from_attributes=True)

    discrepancy_id: UUID
    organization_id: UUID
    audit_plan_id: UUID
    audit_line_id: UUID
    asset_id: UUID
    discrepancy_type: str
    status: str
    expected_state: dict[str, object] | None = None
    observed_state: dict[str, object] | None = None
    notes: str | None = None
    detected_by_user_id: UUID | None = None
    detected_at: datetime
    resolved_by_user_id: UUID | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetAuditAdjustmentCreate(BaseModel):
    """Adjustment request for an audit line discrepancy."""

    adjustment_type: AssetAuditAdjustmentType
    new_value: str | None = None
    notes: str | None = None


class AssetAuditAdjustmentRead(BaseModel):
    """Asset audit adjustment response."""

    model_config = ConfigDict(from_attributes=True)

    audit_adjustment_id: UUID
    organization_id: UUID
    audit_plan_id: UUID
    audit_line_id: UUID
    asset_id: UUID
    adjustment_type: AssetAuditAdjustmentType
    previous_value: str | None = None
    new_value: str | None = None
    notes: str | None = None
    applied_by_user_id: UUID | None = None
    applied_at: datetime
    created_at: datetime
    updated_at: datetime | None = None


class AssetLifecycleEventRead(BaseModel):
    """Asset lifecycle/compliance trail event response."""

    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    organization_id: UUID
    asset_id: UUID
    event_category: str
    event_type: str
    event_at: datetime
    source_type: str | None = None
    source_record_id: UUID | None = None
    actor_user_id: UUID | None = None
    previous_status: str | None = None
    new_status: str | None = None
    previous_location_id: UUID | None = None
    new_location_id: UUID | None = None
    previous_owner_employee_id: UUID | None = None
    new_owner_employee_id: UUID | None = None
    notes: str | None = None
    event_payload: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssetDepreciationRunCreate(BaseModel):
    """Create depreciation run request."""

    fiscal_period_id: UUID
    description: str | None = None


class AssetDepreciationRunRead(BaseModel):
    """Depreciation run response."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    organization_id: UUID
    fiscal_period_id: UUID
    run_number: int
    run_description: str | None = None
    total_depreciation: Decimal
    assets_processed: int
    status: str
    journal_entry_id: UUID | None = None
    posted_at: datetime | None = None


class AssetDepreciationScheduleRead(BaseModel):
    """Depreciation schedule response."""

    model_config = ConfigDict(from_attributes=True)

    schedule_id: UUID
    run_id: UUID
    asset_id: UUID
    cost_basis: Decimal
    accumulated_depreciation_opening: Decimal
    net_book_value_opening: Decimal
    depreciation_amount: Decimal
    accumulated_depreciation_closing: Decimal
    net_book_value_closing: Decimal
    remaining_life_months_opening: int
    remaining_life_months_closing: int
    expense_account_id: UUID
    accumulated_depreciation_account_id: UUID


class MaintenanceRequestCreate(BaseModel):
    """Create maintenance request."""

    asset_id: UUID
    title: str
    description: str | None = None
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    due_date: date | None = None
    requested_by_user_id: UUID | None = None


class MaintenanceRequestRead(BaseModel):
    """Maintenance request response."""

    model_config = ConfigDict(from_attributes=True)

    maintenance_request_id: UUID
    organization_id: UUID
    asset_id: UUID
    request_number: str
    title: str
    description: str | None = None
    priority: MaintenancePriority
    status: MaintenanceRequestStatus
    due_date: date | None = None
    requested_by_user_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    completed_at: datetime | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MaintenanceWorkOrderCreate(BaseModel):
    """Create work order from maintenance request."""

    maintenance_request_id: UUID
    assigned_to_user_id: UUID | None = None
    planned_start_date: datetime | None = None
    estimated_cost: Decimal | None = None


class MaintenanceWorkOrderRead(BaseModel):
    """Maintenance work order response."""

    model_config = ConfigDict(from_attributes=True)

    work_order_id: UUID
    organization_id: UUID
    maintenance_request_id: UUID
    asset_id: UUID
    work_order_number: str
    title: str
    description: str | None = None
    status: MaintenanceWorkOrderStatus
    assigned_to_user_id: UUID | None = None
    planned_start_date: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completion_notes: str | None = None
    estimated_cost: Decimal
    actual_cost: Decimal
    labor_hours: Decimal | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MaintenancePartUseInput(BaseModel):
    """Part usage line input."""

    item_id: UUID
    quantity: Decimal
    notes: str | None = None


class MaintenancePartsUseRequest(BaseModel):
    """Use parts against a work order."""

    fiscal_period_id: UUID
    warehouse_id: UUID
    parts: list[MaintenancePartUseInput]
    trigger_procurement: bool = True
    procurement_requester_id: UUID | None = None
    procurement_department_id: UUID | None = None


class MaintenanceWorkOrderPartRead(BaseModel):
    """Work order part usage response."""

    model_config = ConfigDict(from_attributes=True)

    maintenance_work_order_part_id: UUID
    organization_id: UUID
    work_order_id: UUID
    item_id: UUID
    warehouse_id: UUID | None = None
    requested_quantity: Decimal
    issued_quantity: Decimal
    uom: str | None = None
    status: MaintenanceWorkOrderPartStatus
    issue_transaction_id: UUID | None = None
    procurement_requisition_id: UUID | None = None
    notes: str | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MaintenancePartsUseResult(BaseModel):
    """Result of applying parts to a work order."""

    work_order: MaintenanceWorkOrderRead
    request: MaintenanceRequestRead
    used_parts: list[MaintenanceWorkOrderPartRead]
    pending_parts: list[MaintenanceWorkOrderPartRead]
    procurement_requisition_id: UUID | None = None


class MaintenanceWorkOrderCompleteRequest(BaseModel):
    """Complete a work order."""

    completion_notes: str | None = None
    labor_hours: Decimal | None = None
    additional_cost: Decimal | None = None
