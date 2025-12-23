"""Helpers for validating permissions and org scope access in Finance module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.service import AuthService
from app.common.models import Batch, FinanceEntry
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
        permission: Required permission code (e.g., 'finance.entries.create')

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


def validate_batch_lock_authorization(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    batch_id: UUID,
) -> tuple[UUID, bool]:
    """
    Validate batch lock authorization and return org_unit_id and whether dual verification is complete.

    Args:
        db: Database session
        user_id: ID of the user attempting to lock
        tenant_id: Tenant ID
        batch_id: Batch ID to lock

    Returns:
        Tuple of (org_unit_id, is_ready_to_lock)
        is_ready_to_lock is True if both verifications are complete and users are different

    Raises:
        ValueError: If batch not found, user lacks permission, or org access
    """
    batch = db.execute(
        select(Batch).where(
            Batch.id == batch_id, Batch.tenant_id == tenant_id
        )
    ).scalar_one_or_none()

    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    if batch.status == "locked":
        raise ValueError("Batch is already locked")

    # Check permission and org access
    validate_org_access_for_operation(
        db, user_id, tenant_id, batch.org_unit_id, "finance.batches.lock"
    )

    # Check if this is the first or second verification
    if batch.verified_by_1 is None:
        # First verification
        return batch.org_unit_id, False
    elif batch.verified_by_2 is None:
        # Second verification - must be different user
        if batch.verified_by_1 == user_id:
            raise ValueError(
                "Dual verification requires two different users. "
                "This batch has already been verified by you."
            )
        return batch.org_unit_id, True
    else:
        # Both verifications complete
        if batch.verified_by_1 == user_id or batch.verified_by_2 == user_id:
            raise ValueError(
                "Dual verification requires two different users. "
                "This batch has already been verified by you."
            )
        # Allow locking if both verifications are done by different users
        return batch.org_unit_id, True


def validate_entry_modification(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    entry_id: UUID,
    permission: str,
) -> None:
    """
    Validate that a finance entry can be modified (not locked).

    Args:
        db: Database session
        user_id: ID of the user
        tenant_id: Tenant ID
        entry_id: Finance entry ID
        permission: Required permission code

    Raises:
        ValueError: If entry is locked, user lacks permission, or org access
    """
    entry = db.execute(
        select(FinanceEntry).where(
            FinanceEntry.id == entry_id, FinanceEntry.tenant_id == tenant_id
        )
    ).scalar_one_or_none()

    if not entry:
        raise ValueError(f"Finance entry {entry_id} not found")

    # Check if entry is locked
    if entry.verified_status == "locked":
        raise ValueError("Cannot modify locked finance entry")

    # Check if entry is in a locked batch
    if entry.batch_id:
        batch = db.get(Batch, entry.batch_id)
        if batch and batch.status == "locked":
            raise ValueError("Cannot modify entry in a locked batch")

    # Check permission and org access
    validate_org_access_for_operation(
        db, user_id, tenant_id, entry.org_unit_id, permission
    )

