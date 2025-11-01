"""User provisioning routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.common.db import get_db
from app.core.config import settings
from app.users.schemas import (
    InvitationCreateRequest,
    InvitationResponse,
    UserActivationRequest,
    UserActivationResponse,
    UserCreateRequest,
    UserCreateResponse,
)
from app.users.service import UserProvisioningService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    request: InvitationCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a user invitation."""
    tenant_id = UUID(settings.tenant_id)

    try:
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            email=request.email,
            role_id=request.role_id,
            org_unit_id=request.org_unit_id,
            scope_type=request.scope_type,
            custom_org_unit_ids=request.custom_org_unit_ids,
            twofa_delivery=request.twofa_delivery,
        )
        return InvitationResponse(
            id=invitation.id,
            email=invitation.email,
            expires_at=invitation.expires_at.isoformat(),
            created_at=invitation.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/activate", response_model=UserActivationResponse)
async def activate_user(
    request: UserActivationRequest,
    db: Session = Depends(get_db),
):
    """Activate user from invitation token."""
    tenant_id = UUID(settings.tenant_id)

    try:
        user, _ = UserProvisioningService.activate_user(
            db=db,
            token=request.token,
            password=request.password,
            tenant_id=tenant_id,
        )
        return UserActivationResponse(
            user_id=user.id,
            requires_2fa=True,
            message="User activated. Please complete 2FA setup.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("", response_model=UserCreateResponse)
async def create_user(
    request: UserCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create user directly (onsite scenarios)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        user = UserProvisioningService.create_user_direct(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            email=request.email,
            password=request.password,
            role_id=request.role_id,
            org_unit_id=request.org_unit_id,
            scope_type=request.scope_type,
            custom_org_unit_ids=request.custom_org_unit_ids,
            twofa_delivery=request.twofa_delivery,
        )
        return UserCreateResponse(
            user_id=user.id,
            email=user.email,
            is_active=user.is_active,
            requires_2fa=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

