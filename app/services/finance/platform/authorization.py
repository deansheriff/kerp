"""
AuthorizationService - RBAC permission checks and data scope validation.

Extends existing RBAC with data scope validation and segregation of duties
(SoD) enforcement for IFRS accounting operations.
"""

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person import Person
from app.services.common import coerce_uuid
from app.services.auth_flow import load_effective_rbac_claims
from app.services.response import ListResponseMixin

logger = logging.getLogger(__name__)


class AuthorizationService(ListResponseMixin):
    """
    Service for authorization checks.

    Extends existing RBAC with data scope validation and
    segregation of duties (SoD) enforcement.
    """

    @staticmethod
    def check_permission(
        db: Session,
        user_id: UUID,
        permission_key: str,
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            db: Database session
            user_id: User to check
            permission_key: Permission key (e.g., "gl.journal.post")
            organization_id: Optional organization context

        Returns:
            True if permitted, False otherwise
        """
        uid = coerce_uuid(user_id)
        if organization_id and not AuthorizationService._user_in_org(
            db, uid, coerce_uuid(organization_id)
        ):
            return False

        roles, permissions = load_effective_rbac_claims(db, str(uid))
        normalized_roles = {str(role).strip().lower() for role in roles}
        return "admin" in normalized_roles or permission_key in permissions

    @staticmethod
    def require_permission(
        db: Session,
        user_id: UUID,
        permission_key: str,
        organization_id: UUID | None = None,
    ) -> None:
        """
        Require a permission, raising exception if not granted.

        Args:
            db: Database session
            user_id: User to check
            permission_key: Required permission
            organization_id: Optional organization context

        Raises:
            HTTPException(403): If permission not granted
        """
        if not AuthorizationService.check_permission(
            db, user_id, permission_key, organization_id
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission_key}' required",
            )

    @staticmethod
    def check_role(
        db: Session,
        user_id: UUID,
        role_name: str,
    ) -> bool:
        """
        Check if user has a specific role.

        Args:
            db: Database session
            user_id: User to check
            role_name: Role name to check for

        Returns:
            True if user has role, False otherwise
        """
        uid = coerce_uuid(user_id)

        roles, _ = load_effective_rbac_claims(db, str(uid))
        normalized_roles = {str(role).strip().lower() for role in roles}
        return role_name.strip().lower() in normalized_roles

    @staticmethod
    def require_role(
        db: Session,
        user_id: UUID,
        role_name: str,
    ) -> None:
        """
        Require a role, raising exception if not assigned.

        Args:
            db: Database session
            user_id: User to check
            role_name: Required role

        Raises:
            HTTPException(403): If role not assigned
        """
        if not AuthorizationService.check_role(db, user_id, role_name):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role_name}' required",
            )

    @staticmethod
    def validate_sod(
        db: Session,
        user_id: UUID,
        action_type: str,
        document_id: UUID,
        previous_actors: list[UUID],
    ) -> tuple[bool, str | None]:
        """
        Validate segregation of duties requirements.

        Checks that user is not in conflict with previous actors
        on the document (e.g., creator cannot be approver).

        Args:
            db: Database session
            user_id: User attempting action
            action_type: Type of action (e.g., "APPROVE", "POST")
            document_id: Document being acted upon
            previous_actors: List of previous actor user IDs

        Returns:
            Tuple of (is_valid, violation_reason)
        """
        uid = coerce_uuid(user_id)

        # Check if user is in the list of previous actors
        previous_uuids = [coerce_uuid(a) for a in previous_actors if a]

        if uid in previous_uuids:
            return (
                False,
                f"Segregation of duties violation: user cannot perform "
                f"{action_type} on document they previously acted on",
            )

        return (True, None)

    @staticmethod
    def validate_sod_rule(
        db: Session,
        user_id: UUID,
        rule: str,
        context: dict,
    ) -> tuple[bool, str | None]:
        """
        Validate a specific SoD rule.

        Supported rules:
        - CANNOT_BE_CREATOR: User cannot be the document creator
        - CANNOT_BE_PREVIOUS_APPROVER: User cannot have approved at previous level

        Args:
            db: Database session
            user_id: User attempting action
            rule: SoD rule to validate
            context: Context containing relevant IDs

        Returns:
            Tuple of (is_valid, violation_reason)
        """
        uid = coerce_uuid(user_id)

        if rule == "CANNOT_BE_CREATOR":
            creator_id = context.get("created_by_user_id")
            if creator_id and coerce_uuid(creator_id) == uid:
                return (
                    False,
                    "Segregation of duties: approver cannot be document creator",
                )

        elif rule == "CANNOT_BE_PREVIOUS_APPROVER":
            previous_approvers = context.get("previous_approvers", [])
            if uid in [coerce_uuid(a) for a in previous_approvers if a]:
                return (
                    False,
                    "Segregation of duties: user already approved at previous level",
                )

        return (True, None)

    @staticmethod
    def get_user_permissions(
        db: Session,
        user_id: UUID,
        organization_id: UUID | None = None,
    ) -> list[str]:
        """
        Get all permissions for a user.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Optional organization filter

        Returns:
            List of permission keys
        """
        uid = coerce_uuid(user_id)
        if organization_id and not AuthorizationService._user_in_org(
            db, uid, coerce_uuid(organization_id)
        ):
            return []

        _, permissions = load_effective_rbac_claims(db, str(uid))
        return permissions

    @staticmethod
    def get_user_roles(
        db: Session,
        user_id: UUID,
    ) -> list[str]:
        """
        Get all roles for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of role names
        """
        uid = coerce_uuid(user_id)

        roles, _ = load_effective_rbac_claims(db, str(uid))
        return roles

    @staticmethod
    def check_any_permission(
        db: Session,
        user_id: UUID,
        permission_keys: list[str],
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if user has any of the specified permissions.

        Args:
            db: Database session
            user_id: User to check
            permission_keys: List of permission keys to check
            organization_id: Optional organization context

        Returns:
            True if user has any permission, False otherwise
        """
        for key in permission_keys:
            if AuthorizationService.check_permission(db, user_id, key, organization_id):
                return True
        return False

    @staticmethod
    def check_all_permissions(
        db: Session,
        user_id: UUID,
        permission_keys: list[str],
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if user has all of the specified permissions.

        Args:
            db: Database session
            user_id: User to check
            permission_keys: List of permission keys to check
            organization_id: Optional organization context

        Returns:
            True if user has all permissions, False otherwise
        """
        for key in permission_keys:
            if not AuthorizationService.check_permission(
                db, user_id, key, organization_id
            ):
                return False
        return True

    @staticmethod
    def _user_in_org(
        db: Session,
        user_id: UUID,
        organization_id: UUID,
    ) -> bool:
        return (
            db.scalars(
                select(Person)
                .where(Person.id == user_id)
                .where(Person.organization_id == organization_id)
            ).first()
            is not None
        )


# Module-level singleton instance
authorization_service = AuthorizationService()
