"""User provisioning routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.common.db import get_db
from app.common.models import OrgAssignment
from app.common.request_info import get_request_ip, get_request_user_agent
from app.core.config import settings
from app.users.schemas import (
    InvitationCreateRequest,
    InvitationDetailResponse,
    InvitationListResponse,
    InvitationResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    UserActivationRequest,
    UserActivationResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.users.service import UserManagementService, UserProvisioningService
from app.iam.service import OrgAssignmentService
from app.iam import schemas as iam_schemas

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


# Invitation Management Routes
@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    email: Optional[str] = Query(None),
    invitation_status: Optional[str] = Query(None, pattern="^(pending|used|expired)$"),
    expires_before: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List invitations with optional filters and pagination."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(
            db, user_id, tenant_id, "system.users.read"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Parse expires_before if provided
    expires_before_dt = None
    if expires_before:
        expires_before_dt = datetime.fromisoformat(
            expires_before.replace("Z", "+00:00")
        )

    offset = (page - 1) * per_page
    items, total = UserProvisioningService.list_invitations(
        db=db,
        tenant_id=tenant_id,
        email=email,
        status=invitation_status,
        expires_before=expires_before_dt,
        limit=per_page,
        offset=offset,
    )

    # Convert to response format
    result = []
    for invitation in items:
        # Determine status
        now = datetime.now(timezone.utc)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if invitation.used_at is not None:
            inv_status = "used"
        elif expires_at <= now:
            inv_status = "expired"
        else:
            inv_status = "pending"

        result.append(
            InvitationDetailResponse(
                id=invitation.id,
                email=invitation.email,
                expires_at=invitation.expires_at.isoformat(),
                created_at=invitation.created_at.isoformat(),
                used_at=invitation.used_at.isoformat() if invitation.used_at else None,
                invited_by=invitation.invited_by,
                role_id=invitation.role_id,
                org_unit_id=invitation.org_unit_id,
                scope_type=invitation.scope_type,
                twofa_delivery=invitation.twofa_delivery,
                status=inv_status,
            )
        )

    return InvitationListResponse(
        items=result,
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/invitations/{invitation_id}", response_model=InvitationDetailResponse)
async def get_invitation(
    invitation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get invitation details."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(
            db, current_user_id, tenant_id, "system.users.read"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    invitation = UserProvisioningService.get_invitation(
        db, invitation_id, tenant_id
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invitation {invitation_id} not found",
        )

    # Determine status
    now = datetime.now(timezone.utc)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation.used_at is not None:
        inv_status = "used"
    elif expires_at <= now:
        inv_status = "expired"
    else:
        inv_status = "pending"

    return InvitationDetailResponse(
        id=invitation.id,
        email=invitation.email,
        expires_at=invitation.expires_at.isoformat(),
        created_at=invitation.created_at.isoformat(),
        used_at=invitation.used_at.isoformat() if invitation.used_at else None,
        invited_by=invitation.invited_by,
        role_id=invitation.role_id,
        org_unit_id=invitation.org_unit_id,
        scope_type=invitation.scope_type,
        twofa_delivery=invitation.twofa_delivery,
        status=inv_status,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation(
    invitation_id: UUID,
    http_request: Request,
    resender_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Resend an invitation email."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        invitation = UserProvisioningService.resend_invitation(
            db=db,
            resender_id=resender_id,
            tenant_id=tenant_id,
            invitation_id=invitation_id,
            ip=ip,
            user_agent=user_agent,
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


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    invitation_id: UUID,
    http_request: Request,
    canceller_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Cancel an invitation."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        UserProvisioningService.cancel_invitation(
            db=db,
            canceller_id=canceller_id,
            tenant_id=tenant_id,
            invitation_id=invitation_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# User Management Routes
@router.get("", response_model=UserListResponse)
async def list_users(
    org_unit_id: Optional[UUID] = Query(None),
    role_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List users with optional filters and pagination."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.users.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    offset = (page - 1) * per_page
    items, total = UserManagementService.list_users(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        role_id=role_id,
        is_active=is_active,
        search=search,
        limit=per_page,
        offset=offset,
    )

    # Get assignment counts for each user
    result = []
    for user in items:
        assignment_count = db.execute(
            select(func.count()).select_from(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == tenant_id,
            )
        ).scalar() or 0

        result.append(
            UserResponse(
                id=user.id,
                email=user.email,
                is_active=user.is_active,
                is_2fa_enabled=user.is_2fa_enabled,
                created_at=user.created_at.isoformat(),
                updated_at=user.updated_at.isoformat(),
                assignments_count=assignment_count,
            )
        )

    return UserListResponse(
        items=result,
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get user details."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(
            db, current_user_id, tenant_id, "system.users.read"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    user = UserManagementService.get_user(db, user_id, tenant_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Get assignment count
    assignment_count = db.execute(
        select(func.count()).select_from(OrgAssignment).where(
            OrgAssignment.user_id == user.id,
            OrgAssignment.tenant_id == tenant_id,
        )
    ).scalar() or 0

    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_2fa_enabled=user.is_2fa_enabled,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
        assignments_count=assignment_count,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    http_request: Request,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a user."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        user = UserManagementService.update_user(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            user_id=user_id,
            email=request.email,
            is_active=request.is_active,
            is_2fa_enabled=request.is_2fa_enabled,
            ip=ip,
            user_agent=user_agent,
        )

        # Get assignment count
        assignment_count = db.execute(
            select(func.count()).select_from(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == tenant_id,
            )
        ).scalar() or 0

        return UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            assignments_count=assignment_count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    http_request: Request,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a user (soft delete)."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        UserManagementService.delete_user(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            user_id=user_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: UUID,
    http_request: Request,
    disabler_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Disable a user account."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        user = UserManagementService.disable_user(
            db=db,
            disabler_id=disabler_id,
            tenant_id=tenant_id,
            user_id=user_id,
            ip=ip,
            user_agent=user_agent,
        )

        # Get assignment count
        assignment_count = db.execute(
            select(func.count()).select_from(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == tenant_id,
            )
        ).scalar() or 0

        return UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            assignments_count=assignment_count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{user_id}/enable", response_model=UserResponse)
async def enable_user(
    user_id: UUID,
    http_request: Request,
    enabler_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Enable a user account."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        user = UserManagementService.enable_user(
            db=db,
            enabler_id=enabler_id,
            tenant_id=tenant_id,
            user_id=user_id,
            ip=ip,
            user_agent=user_agent,
        )

        # Get assignment count
        assignment_count = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == tenant_id,
            )
        ).scalar() or 0

        return UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            assignments_count=assignment_count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    user_id: UUID,
    request: PasswordResetRequest,
    http_request: Request,
    resetter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Reset a user's password (admin action)."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        UserManagementService.reset_password(
            db=db,
            resetter_id=resetter_id,
            tenant_id=tenant_id,
            user_id=user_id,
            new_password=request.new_password,
            ip=ip,
            user_agent=user_agent,
        )
        return PasswordResetResponse()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{user_id}/change-password", response_model=PasswordResetResponse)
async def change_password(
    user_id: UUID,
    request: PasswordChangeRequest,
    http_request: Request,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Change user's own password (requires current password)."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    # Verify user is changing their own password
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own password",
        )

    try:
        UserManagementService.change_password(
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            current_password=request.current_password,
            new_password=request.new_password,
            ip=ip,
            user_agent=user_agent,
        )
        return PasswordResetResponse(message="Password changed successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Org Assignment Routes
@router.get("/{user_id}/assignments", response_model=list[iam_schemas.OrgAssignmentResponse])
async def list_user_assignments(
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List all assignments for a user."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(
            db, current_user_id, tenant_id, "system.users.read"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    assignments = OrgAssignmentService.list_user_assignments(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
    )

    # Enrich with org unit and role info
    result = []
    for assignment in assignments:
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit

        org_unit = db.get(OrgUnit, assignment.org_unit_id)
        role = db.get(Role, assignment.role_id)

        # Get custom units if scope_type is custom_set
        custom_org_unit_ids = None
        if assignment.scope_type == "custom_set":
            custom_units = db.execute(
                select(OrgAssignmentUnit).where(
                    OrgAssignmentUnit.assignment_id == assignment.id
                )
            ).scalars().all()
            custom_org_unit_ids = [unit.org_unit_id for unit in custom_units]

        result.append(
            iam_schemas.OrgAssignmentResponse(
                id=assignment.id,
                user_id=assignment.user_id,
                org_unit_id=assignment.org_unit_id,
                role_id=assignment.role_id,
                scope_type=assignment.scope_type,
                org_unit=iam_schemas.OrgUnitInfo.model_validate(org_unit) if org_unit else None,
                role=iam_schemas.RoleInfo.model_validate(role) if role else None,
                custom_org_unit_ids=custom_org_unit_ids,
            )
        )

    return result


@router.post("/{user_id}/assignments", response_model=iam_schemas.OrgAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    user_id: UUID,
    request: iam_schemas.OrgAssignmentCreateRequest,
    http_request: Request,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new org assignment for a user."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        assignment = OrgAssignmentService.create_assignment(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            user_id=user_id,
            org_unit_id=request.org_unit_id,
            role_id=request.role_id,
            scope_type=request.scope_type,
            custom_org_unit_ids=request.custom_org_unit_ids,
            ip=ip,
            user_agent=user_agent,
        )

        # Enrich with org unit and role info
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit

        org_unit = db.get(OrgUnit, assignment.org_unit_id)
        role = db.get(Role, assignment.role_id)

        # Get custom units if scope_type is custom_set
        custom_org_unit_ids = None
        if assignment.scope_type == "custom_set":
            custom_units = db.execute(
                select(OrgAssignmentUnit).where(
                    OrgAssignmentUnit.assignment_id == assignment.id
                )
            ).scalars().all()
            custom_org_unit_ids = [unit.org_unit_id for unit in custom_units]

        return iam_schemas.OrgAssignmentResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            org_unit_id=assignment.org_unit_id,
            role_id=assignment.role_id,
            scope_type=assignment.scope_type,
            org_unit=iam_schemas.OrgUnitInfo.model_validate(org_unit) if org_unit else None,
            role=iam_schemas.RoleInfo.model_validate(role) if role else None,
            custom_org_unit_ids=custom_org_unit_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch("/{user_id}/assignments/{assignment_id}", response_model=iam_schemas.OrgAssignmentResponse)
async def update_assignment(
    user_id: UUID,
    assignment_id: UUID,
    request: iam_schemas.OrgAssignmentUpdateRequest,
    http_request: Request,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update an org assignment."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        assignment = OrgAssignmentService.update_assignment(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            role_id=request.role_id,
            scope_type=request.scope_type,
            ip=ip,
            user_agent=user_agent,
        )

        # Enrich with org unit and role info
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit

        org_unit = db.get(OrgUnit, assignment.org_unit_id)
        role = db.get(Role, assignment.role_id)

        # Get custom units if scope_type is custom_set
        custom_org_unit_ids = None
        if assignment.scope_type == "custom_set":
            custom_units = db.execute(
                select(OrgAssignmentUnit).where(
                    OrgAssignmentUnit.assignment_id == assignment.id
                )
            ).scalars().all()
            custom_org_unit_ids = [unit.org_unit_id for unit in custom_units]

        return iam_schemas.OrgAssignmentResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            org_unit_id=assignment.org_unit_id,
            role_id=assignment.role_id,
            scope_type=assignment.scope_type,
            org_unit=iam_schemas.OrgUnitInfo.model_validate(org_unit) if org_unit else None,
            role=iam_schemas.RoleInfo.model_validate(role) if role else None,
            custom_org_unit_ids=custom_org_unit_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/{user_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    user_id: UUID,
    assignment_id: UUID,
    http_request: Request,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete an org assignment."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        OrgAssignmentService.delete_assignment(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{user_id}/assignments/{assignment_id}/units", response_model=iam_schemas.OrgAssignmentResponse)
async def add_custom_unit(
    user_id: UUID,
    assignment_id: UUID,
    request: iam_schemas.CustomUnitAddRequest,
    http_request: Request,
    adder_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Add an org unit to a custom_set assignment."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        OrgAssignmentService.add_custom_unit(
            db=db,
            adder_id=adder_id,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            org_unit_id=request.org_unit_id,
            ip=ip,
            user_agent=user_agent,
        )

        # Return updated assignment
        assignment = db.get(OrgAssignment, assignment_id)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found",
            )

        # Enrich with org unit and role info
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit

        org_unit = db.get(OrgUnit, assignment.org_unit_id)
        role = db.get(Role, assignment.role_id)

        # Get custom units
        custom_units = db.execute(
            select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assignment.id
            )
        ).scalars().all()
        custom_org_unit_ids = [unit.org_unit_id for unit in custom_units]

        return iam_schemas.OrgAssignmentResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            org_unit_id=assignment.org_unit_id,
            role_id=assignment.role_id,
            scope_type=assignment.scope_type,
            org_unit=iam_schemas.OrgUnitInfo.model_validate(org_unit) if org_unit else None,
            role=iam_schemas.RoleInfo.model_validate(role) if role else None,
            custom_org_unit_ids=custom_org_unit_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/{user_id}/assignments/{assignment_id}/units/{org_unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_custom_unit(
    user_id: UUID,
    assignment_id: UUID,
    org_unit_id: UUID,
    http_request: Request,
    remover_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Remove an org unit from a custom_set assignment."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        OrgAssignmentService.remove_custom_unit(
            db=db,
            remover_id=remover_id,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            org_unit_id=org_unit_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
