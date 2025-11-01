"""
Row-Level Security (RLS) session management.

This module provides utilities to set PostgreSQL session variables for RLS
enforcement. These variables are used by RLS policies to filter rows based on
tenant, user, and permissions.

Note: RLS is PostgreSQL-specific and does not work with SQLite.
This module automatically detects SQLite and skips RLS operations.

Session variables:
- app.tenant_id: UUID of the current tenant
- app.user_id: UUID of the current user (or NULL for unauthenticated)
- app.perms: text[] array of permission codes for the current user
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def _is_postgresql(db: Session) -> bool:
    """Check if the database is PostgreSQL."""
    try:
        dialect_name = db.bind.dialect.name if db.bind else None
        return dialect_name == "postgresql"
    except (AttributeError, TypeError):
        return False


def set_rls_context(
    db: Session,
    tenant_id: UUID,
    user_id: Optional[UUID] = None,
    permissions: Optional[list[str]] = None,
) -> None:
    """
    Set PostgreSQL session variables for RLS enforcement.

    Args:
        db: Database session
        tenant_id: Current tenant ID
        user_id: Current user ID (None for unauthenticated requests)
        permissions: List of permission codes for the current user

    Note:
        This function is a no-op for non-PostgreSQL databases (e.g., SQLite).
        RLS is PostgreSQL-specific and not supported in SQLite.
    """
    if not settings.enable_rls:
        return

    # Skip RLS operations for non-PostgreSQL databases (e.g., SQLite)
    if not _is_postgresql(db):
        return

    # Set tenant_id (always required)
    # Note: SET LOCAL doesn't support parameterized queries, so we use
    # string formatting. The tenant_id comes from validated UUID sources.
    tenant_id_str = str(tenant_id)
    db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'"))

    # Set user_id (can be NULL for public endpoints)
    # Note: SET LOCAL doesn't support NULL directly, so we skip setting it
    # if user_id is None. PostgreSQL will treat an unset variable as NULL
    # in RLS policies.
    if user_id:
        user_id_str = str(user_id)
        db.execute(text(f"SET LOCAL app.user_id = '{user_id_str}'"))

    # Set permissions array
    if permissions:
        # Convert to PostgreSQL array literal
        perms_array = "{" + ",".join(f'"{p}"' for p in permissions) + "}"
        db.execute(text(f"SET LOCAL app.perms = '{perms_array}'"))
    else:
        db.execute(text("SET LOCAL app.perms = '{}'"))


def clear_rls_context(db: Session) -> None:
    """
    Clear RLS session variables (useful for cleanup or testing).

    Args:
        db: Database session

    Note:
        This function is a no-op for non-PostgreSQL databases (e.g., SQLite).
    """
    if not settings.enable_rls:
        return

    # Skip RLS operations for non-PostgreSQL databases (e.g., SQLite)
    if not _is_postgresql(db):
        return

    # Note: SET LOCAL variables are automatically cleared at the end of the
    # transaction, so explicit clearing isn't necessary. However, if we want
    # to clear them within a transaction, we can set them to empty values.
    # Since RESET doesn't work with SET LOCAL variables, we set them to
    # empty strings (which RLS policies should treat as no match).
    # In practice, these will be automatically cleared when the transaction
    # ends. This function is mainly for explicit cleanup if needed.
    try:
        db.execute(text("SET LOCAL app.tenant_id = ''"))
        db.execute(text("SET LOCAL app.user_id = ''"))
        db.execute(text("SET LOCAL app.perms = ''"))
    except Exception:  # noqa: BLE001
        # If clearing fails, variables will still be cleared at transaction end
        pass
