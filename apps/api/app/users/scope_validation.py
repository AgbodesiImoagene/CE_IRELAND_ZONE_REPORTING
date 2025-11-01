"""Helpers for validating org scope access during user provisioning."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.common.models import OrgAssignment, OrgUnit, OrgAssignmentUnit


def has_org_access(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    target_org_unit_id: UUID,
) -> bool:
    """
    Check if user has access to target org unit based on their assignments.

    Handles:
    - 'self': exact match
    - 'subtree': target is descendant of assigned org
    - 'custom_set': target is in custom_units list
    """
    stmt = select(OrgAssignment).where(
        OrgAssignment.user_id == user_id,
        OrgAssignment.tenant_id == tenant_id,
    )
    assignments = db.execute(stmt).scalars().all()

    for assn in assignments:
        if assn.scope_type == "self":
            if assn.org_unit_id == target_org_unit_id:
                return True
        elif assn.scope_type == "subtree":
            # Check if target_org_unit_id is descendant of assn.org_unit_id
            if _is_descendant(db, target_org_unit_id, assn.org_unit_id):
                return True
        elif assn.scope_type == "custom_set":
            # Check custom_units
            stmt_units = select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assn.id,
                OrgAssignmentUnit.org_unit_id == target_org_unit_id,
            )
            if db.execute(stmt_units).scalar_one_or_none():
                return True

    return False


def _is_descendant(db: Session, target_id: UUID, ancestor_id: UUID) -> bool:
    """Check if target org unit is a descendant of ancestor."""
    if target_id == ancestor_id:
        return True

    # Walk up the parent chain
    current = db.get(OrgUnit, target_id)
    while current and current.parent_id:
        if current.parent_id == ancestor_id:
            return True
        current = db.get(OrgUnit, current.parent_id)

    return False


def validate_scope_assignments(
    db: Session,
    creator_id: UUID,
    tenant_id: UUID,
    target_org_unit_id: UUID,
    target_role_id: UUID,
) -> None:
    """
    Validate that creator can assign the given role/scope combination.

    Raises ValueError if validation fails.
    """
    # Check permission
    from app.auth.service import AuthService

    perms = AuthService.get_user_permissions(db, creator_id, tenant_id)
    if "system.users.create" not in perms:
        raise ValueError("User lacks system.users.create permission")

    # Check org access
    if not has_org_access(db, creator_id, tenant_id, target_org_unit_id):
        raise ValueError(
            f"User does not have access to org unit {target_org_unit_id}"
        )

    # TODO: Additional validation:
    # - Can only assign roles that are "below" creator's own role level
    # - Zonal Pastor can assign any role
    # - Group Pastor can only assign church-level roles
    # - Church Pastor can only assign portal roles (Church Admin, Finance
    #   Officer, Cell Leader)

