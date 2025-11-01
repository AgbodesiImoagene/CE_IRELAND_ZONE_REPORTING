from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.utils import verify_token
from app.auth.service import AuthService
from app.common.db import get_db
from app.core.config import settings
from app.core.rls import set_rls_context

security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UUID:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return UUID(user_id)


def get_db_with_rls(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> Session:
    """
    Database dependency with RLS context for authenticated requests.

    Use this instead of get_db when RLS should be enforced.
    """
    tenant_id = UUID(settings.tenant_id)
    permissions = AuthService.get_user_permissions(db, user_id, tenant_id)

    set_rls_context(db, tenant_id, user_id, permissions)

    return db


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
) -> dict:
    """Get current user info with RLS context set."""
    return AuthService.get_user_info(db, user_id, UUID(settings.tenant_id))


def setup_rls_context(
    db: Session = Depends(get_db),
    user_id: Optional[UUID] = Depends(lambda: None),
) -> Session:
    """
    Dependency to set RLS context for authenticated requests.

    For unauthenticated requests, use get_db directly.
    For authenticated requests, use get_db_with_rls instead.
    """
    tenant_id = UUID(settings.tenant_id)

    # Get user permissions if authenticated
    permissions = None
    if user_id:
        permissions = AuthService.get_user_permissions(db, user_id, tenant_id)

    # Set RLS context
    set_rls_context(db, tenant_id, user_id, permissions)

    return db
