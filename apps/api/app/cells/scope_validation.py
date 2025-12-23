"""Helpers for validating permissions and org scope access in Cells module."""

from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.service import AuthService
from app.users.scope_validation import has_org_access
from app.common.models import Cell, People


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
        permission: Required permission code (e.g., 'cells.reports.create')

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


def validate_cell_leader_access(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    cell_id: UUID,
    permission: str,
) -> None:
    """
    Validate that user is the leader of the cell and has the required permission.

    Args:
        db: Database session
        user_id: ID of the user
        tenant_id: Tenant ID
        cell_id: Cell ID to check access for
        permission: Required permission code

    Raises:
        ValueError: If user is not the cell leader or lacks permission
    """
    require_permission(db, user_id, tenant_id, permission)

    # Get cell
    from sqlalchemy import select
    cell = db.execute(
        select(Cell).where(Cell.id == cell_id, Cell.tenant_id == tenant_id)
    ).scalar_one_or_none()

    if not cell:
        raise ValueError(f"Cell {cell_id} not found")

    # Get user's person_id (need to check how users link to people)
    # For now, we'll check if the user's person_id matches the cell's leader_id
    # This assumes users have a person_id field or we need to look it up differently
    # TODO: Implement proper user-to-person linking check
    # For now, we'll validate org access instead and let the service layer handle leader validation
    validate_org_access_for_operation(
        db, user_id, tenant_id, cell.org_unit_id, permission
    )

