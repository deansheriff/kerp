"""
ERPNext Sync Tasks - Celery background tasks for data synchronization.

These tasks handle:
- Full sync of all entities from ERPNext
- Incremental sync of modified records
- Entity-specific sync for retrying failures
- Outbound sync to push changes back to ERPNext
"""

import logging

from celery import shared_task
from sqlalchemy.orm import Session

from app.models.finance.core_org.organization import Organization
from app.models.sync import IntegrationType
from app.services.erpnext.client import ERPNextConfig

logger = logging.getLogger(__name__)
API_SYNC_DISABLED_MSG = "ERPNext API sync is disabled. Use SQL-based sync only."


def _get_erpnext_config(db: "Session", org: Organization) -> ERPNextConfig | None:
    """
    Get ERPNext configuration from IntegrationConfig table.

    Looks up ERPNext integration settings for the organization.
    Decrypts credentials if they are encrypted.
    Returns None if ERPNext integration is not configured.
    """
    from app.services.integration_config import IntegrationConfigService

    service = IntegrationConfigService(db)
    creds = service.get_decrypted_credentials(
        org.organization_id,
        IntegrationType.ERPNEXT,
    )

    if not creds:
        return None

    if not creds["base_url"] or not creds["api_key"] or not creds["api_secret"]:
        return None

    return ERPNextConfig(
        url=creds["base_url"],
        api_key=creds["api_key"],
        api_secret=creds["api_secret"],
        company=creds.get("company"),
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_full_erpnext_sync(
    self,
    organization_id: str,
    user_id: str,
    entity_types: list[str] | None = None,
) -> dict:
    """
    Run full ERPNext sync for an organization.

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the user initiating the sync
        entity_types: Optional list of entity types to sync (default: all)

    Returns:
        Dict with sync statistics
    """
    logger.warning(
        "Blocked ERPNext API full sync for organization %s: %s",
        organization_id,
        API_SYNC_DISABLED_MSG,
    )
    return {"success": False, "error": API_SYNC_DISABLED_MSG, "disabled": True}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_incremental_erpnext_sync(
    self,
    organization_id: str,
    user_id: str,
    entity_types: list[str] | None = None,
) -> dict:
    """
    Run incremental ERPNext sync - only sync records modified since last sync.

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the user initiating the sync
        entity_types: Optional list of entity types to sync

    Returns:
        Dict with sync statistics
    """
    logger.warning(
        "Blocked ERPNext API incremental sync for organization %s: %s",
        organization_id,
        API_SYNC_DISABLED_MSG,
    )
    return {"success": False, "error": API_SYNC_DISABLED_MSG, "disabled": True}


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def sync_single_entity_type(
    self,
    organization_id: str,
    user_id: str,
    entity_type: str,
    incremental: bool = True,
) -> dict:
    """
    Sync a single entity type from ERPNext.

    Useful for:
    - Retrying failed entity types
    - Testing sync configuration
    - On-demand refresh of specific data

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the user
        entity_type: The entity type to sync (e.g., "employees", "departments")
        incremental: Whether to do incremental sync

    Returns:
        Dict with sync statistics
    """
    logger.warning(
        "Blocked ERPNext API entity sync (%s) for organization %s: %s",
        entity_type,
        organization_id,
        API_SYNC_DISABLED_MSG,
    )
    return {"success": False, "error": API_SYNC_DISABLED_MSG, "disabled": True}


@shared_task
def scheduled_hr_sync() -> dict:
    """
    Scheduled task to sync HR data from ERPNext for all configured organizations.

    This task runs on a schedule (e.g., every hour) to keep HR data current.
    Only syncs HR-related entities: employees, departments, leave, attendance.

    Organizations are found by looking at successful SyncHistory records,
    meaning they must have completed at least one manual sync first.
    """
    logger.warning("Blocked scheduled ERPNext HR sync: %s", API_SYNC_DISABLED_MSG)
    return {
        "organizations_processed": 0,
        "results": [],
        "disabled": True,
        "error": API_SYNC_DISABLED_MSG,
    }


@shared_task
def scheduled_expense_sync() -> dict:
    """
    Scheduled task to sync expense data from ERPNext.

    Runs less frequently than HR sync since expense data changes less often.

    Organizations are found by looking at successful SyncHistory records,
    meaning they must have completed at least one manual sync first.
    """
    logger.warning("Blocked scheduled ERPNext expense sync: %s", API_SYNC_DISABLED_MSG)
    return {
        "organizations_processed": 0,
        "results": [],
        "disabled": True,
        "error": API_SYNC_DISABLED_MSG,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def push_expense_claim_to_erpnext(
    self,
    organization_id: str,
    user_id: str,
    claim_id: str,
    submit: bool = False,
) -> dict:
    """
    Push a single expense claim to ERPNext.

    Used when creating/updating expense claims in DotMac to sync back to ERPNext.

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the user
        claim_id: UUID of the expense claim to push
        submit: Whether to submit the claim in ERPNext (for approval workflow)

    Returns:
        Dict with result
    """
    logger.warning(
        "Blocked outbound ERPNext API expense push (claim=%s): %s",
        claim_id,
        API_SYNC_DISABLED_MSG,
    )
    return {"success": False, "error": API_SYNC_DISABLED_MSG, "disabled": True}
