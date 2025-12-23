"""Helpers for validating permissions and org scope access in Registry module."""

from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.service import AuthService
from app.users.scope_validation import has_org_access


def require_permission(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    permission: str,
) -> None:
    """
    Check if user has the required permission.

    Args:
        db: Database session
        user_id: ID of the user
        tenant_id: Tenant ID
        permission: Required permission code (e.g., 'registry.people.create')

    Raises:
        ValueError: If user does not have the permission
    """
    perms = AuthService.get_user_permissions(db, user_id, tenant_id)
    if permission not in perms:
        raise ValueError(f"User lacks required permission: {permission}")


def validate_org_access_for_operation(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    target_org_unit_id: UUID,
    permission: str,
) -> None:
    """
    Validate that user has both the required permission and org access.

    Args:
        db: Database session
        user_id: ID of the user
        tenant_id: Tenant ID
        target_org_unit_id: Target org unit ID to check access for
        permission: Required permission code

    Raises:
        ValueError: If user lacks permission or org access
    """
    require_permission(db, user_id, tenant_id, permission)

    if not has_org_access(db, user_id, tenant_id, target_org_unit_id):
        raise ValueError(
            f"User does not have access to org unit {target_org_unit_id}"
        )

