"""People assets services."""

from app.services.people.assets.assignment_service import AssetAssignmentService
from app.services.people.assets.audit_service import AssetAuditService
from app.services.people.assets.depreciation_service import PeopleAssetDepreciationService
from app.services.people.assets.maintenance_service import AssetMaintenanceService
from app.services.people.assets.tracking_service import AssetTrackingService

__all__ = [
    "AssetAssignmentService",
    "AssetAuditService",
    "PeopleAssetDepreciationService",
    "AssetMaintenanceService",
    "AssetTrackingService",
]
