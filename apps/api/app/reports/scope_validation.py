"""Helpers for validating permissions in Reports module."""

from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.service import AuthService


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
        permission: Required permission code (e.g., 'reports.dashboards.read')

    Raises:
        ValueError: If user does not have the permission
    """
    perms = AuthService.get_user_permissions(db, user_id, tenant_id)
    if permission not in perms:
        raise ValueError(f"User lacks required permission: {permission}")


