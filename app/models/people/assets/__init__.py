"""
People assets models.
"""

from app.models.people.assets.assignment import (
    AssetAssignment,
    AssetAssignmentMovement,
    AssetCondition,
    AssignmentMovementType,
    AssignmentStatus,
)
from app.models.people.assets.audit import (
    AssetAuditAdjustment,
    AssetAuditAdjustmentType,
    AssetAuditLine,
    AssetAuditLineStatus,
    AssetAuditDiscrepancy,
    AssetAuditPlan,
    AssetAuditPlanStatus,
    AssetLifecycleEvent,
)
from app.models.people.assets.tracking import AssetTrackingEvent, AssetTrackingMethod

__all__ = [
    "AssetAssignment",
    "AssetAssignmentMovement",
    "AssignmentStatus",
    "AssignmentMovementType",
    "AssetCondition",
    "AssetTrackingEvent",
    "AssetTrackingMethod",
    "AssetAuditPlan",
    "AssetAuditPlanStatus",
    "AssetAuditLine",
    "AssetAuditLineStatus",
    "AssetAuditAdjustment",
    "AssetAuditAdjustmentType",
    "AssetAuditDiscrepancy",
    "AssetLifecycleEvent",
]
