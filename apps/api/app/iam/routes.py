"""IAM API routes for org units, roles, permissions, assignments, and audit logs."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.common.db import get_db
from app.common.request_info import get_request_ip, get_request_user_agent
from app.core.config import settings
from app.iam import schemas
from app.iam.service import (
    AuditLogService,
    OrgAssignmentService,
    OrgUnitService,
    RoleService,
    PermissionService,
)

router = APIRouter(prefix="/iam", tags=["iam"])


# Org Units Routes
@router.get("/org-units", response_model=schemas.OrgUnitListResponse)
async def list_org_units(
    type: Optional[str] = Query(None, pattern="^(region|zone|group|church|outreach)$"),
    parent_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List org units with optional filters and pagination."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.org_units.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    offset = (page - 1) * per_page
    items, total = OrgUnitService.list_org_units(
        db=db,
        tenant_id=tenant_id,
        type_filter=type,
        parent_id=parent_id,
        search=search,
        limit=per_page,
        offset=offset,
    )

    return schemas.OrgUnitListResponse(
        items=[schemas.OrgUnitResponse.model_validate(item) for item in items],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/org-units/{org_unit_id}", response_model=schemas.OrgUnitResponse)
async def get_org_unit(
    org_unit_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get org unit details."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.org_units.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
    if not org_unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Org unit {org_unit_id} not found",
        )

    return schemas.OrgUnitResponse.model_validate(org_unit)


@router.post("/org-units", response_model=schemas.OrgUnitResponse, status_code=status.HTTP_201_CREATED)
async def create_org_unit(
    request: schemas.OrgUnitCreateRequest,
    http_request: Request,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new org unit."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        org_unit = OrgUnitService.create_org_unit(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            name=request.name,
            type=request.type,
            parent_id=request.parent_id,
            ip=ip,
            user_agent=user_agent,
        )
        return schemas.OrgUnitResponse.model_validate(org_unit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch("/org-units/{org_unit_id}", response_model=schemas.OrgUnitResponse)
async def update_org_unit(
    org_unit_id: UUID,
    request: schemas.OrgUnitUpdateRequest,
    http_request: Request,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update an org unit."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        org_unit = OrgUnitService.update_org_unit(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            name=request.name,
            parent_id=request.parent_id,
            ip=ip,
            user_agent=user_agent,
        )
        return schemas.OrgUnitResponse.model_validate(org_unit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/org-units/{org_unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_unit(
    org_unit_id: UUID,
    http_request: Request,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete an org unit."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        OrgUnitService.delete_org_unit(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/org-units/{org_unit_id}/children", response_model=list[schemas.OrgUnitResponse])
async def get_org_unit_children(
    org_unit_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get direct children of an org unit."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.org_units.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Verify org unit exists
    org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
    if not org_unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Org unit {org_unit_id} not found",
        )

    children = OrgUnitService.get_children(db, org_unit_id, tenant_id)
    return [schemas.OrgUnitResponse.model_validate(child) for child in children]


@router.get("/org-units/{org_unit_id}/tree", response_model=list[schemas.OrgUnitResponse])
async def get_org_unit_tree(
    org_unit_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get all descendants of an org unit (subtree)."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.org_units.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Verify org unit exists
    org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
    if not org_unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Org unit {org_unit_id} not found",
        )

    subtree = OrgUnitService.get_subtree(db, org_unit_id, tenant_id)
    return [schemas.OrgUnitResponse.model_validate(unit) for unit in subtree]


@router.get("/org-units/{org_unit_id}/ancestors", response_model=list[schemas.OrgUnitResponse])
async def get_org_unit_ancestors(
    org_unit_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get all ancestors of an org unit (path to root)."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.org_units.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Verify org unit exists
    org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
    if not org_unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Org unit {org_unit_id} not found",
        )

    ancestors = OrgUnitService.get_ancestors(db, org_unit_id, tenant_id)
    return [schemas.OrgUnitResponse.model_validate(ancestor) for ancestor in ancestors]


# Roles Routes
@router.get("/roles", response_model=schemas.RoleListResponse)
async def list_roles(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List roles with pagination."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.roles.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    offset = (page - 1) * per_page
    items, total = RoleService.list_roles(
        db=db,
        tenant_id=tenant_id,
        limit=per_page,
        offset=offset,
    )

    # Load permissions for each role
    result = []
    for role in items:
        permissions = RoleService.get_role_permissions(db, role.id, tenant_id)
        result.append(
            schemas.RoleResponse(
                id=role.id,
                name=role.name,
                tenant_id=role.tenant_id,
                permissions=[schemas.PermissionResponse.model_validate(p) for p in permissions],
            )
        )

    return schemas.RoleListResponse(
        items=result,
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/roles/{role_id}", response_model=schemas.RoleResponse)
async def get_role(
    role_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get role details with permissions."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.roles.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    role = RoleService.get_role(db, role_id, tenant_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role {role_id} not found",
        )

    permissions = RoleService.get_role_permissions(db, role_id, tenant_id)
    return schemas.RoleResponse(
        id=role.id,
        name=role.name,
        tenant_id=role.tenant_id,
        permissions=[schemas.PermissionResponse.model_validate(p) for p in permissions],
    )


@router.post("/roles", response_model=schemas.RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    request: schemas.RoleCreateRequest,
    http_request: Request,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new role."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        role = RoleService.create_role(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            name=request.name,
            ip=ip,
            user_agent=user_agent,
        )
        permissions = RoleService.get_role_permissions(db, role.id, tenant_id)
        return schemas.RoleResponse(
            id=role.id,
            name=role.name,
            tenant_id=role.tenant_id,
            permissions=[schemas.PermissionResponse.model_validate(p) for p in permissions],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch("/roles/{role_id}", response_model=schemas.RoleResponse)
async def update_role(
    role_id: UUID,
    request: schemas.RoleUpdateRequest,
    http_request: Request,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a role."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        role = RoleService.update_role(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            role_id=role_id,
            name=request.name,
            ip=ip,
            user_agent=user_agent,
        )
        permissions = RoleService.get_role_permissions(db, role_id, tenant_id)
        return schemas.RoleResponse(
            id=role.id,
            name=role.name,
            tenant_id=role.tenant_id,
            permissions=[schemas.PermissionResponse.model_validate(p) for p in permissions],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    http_request: Request,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a role."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        RoleService.delete_role(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            role_id=role_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/roles/{role_id}/permissions", response_model=list[schemas.PermissionResponse])
async def get_role_permissions(
    role_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get all permissions for a role."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.roles.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Verify role exists
    role = RoleService.get_role(db, role_id, tenant_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role {role_id} not found",
        )

    permissions = RoleService.get_role_permissions(db, role_id, tenant_id)
    return [schemas.PermissionResponse.model_validate(p) for p in permissions]


@router.post("/roles/{role_id}/permissions", response_model=list[schemas.PermissionResponse])
async def assign_permissions(
    role_id: UUID,
    request: schemas.RolePermissionAssignRequest,
    http_request: Request,
    assigner_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Assign permissions to a role."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        permissions = RoleService.assign_permissions(
            db=db,
            assigner_id=assigner_id,
            tenant_id=tenant_id,
            role_id=role_id,
            permission_ids=request.permission_ids,
            ip=ip,
            user_agent=user_agent,
        )
        return [schemas.PermissionResponse.model_validate(p) for p in permissions]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission(
    role_id: UUID,
    permission_id: UUID,
    http_request: Request,
    remover_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Remove a permission from a role."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        RoleService.remove_permission(
            db=db,
            remover_id=remover_id,
            tenant_id=tenant_id,
            role_id=role_id,
            permission_id=permission_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put("/roles/{role_id}/permissions", response_model=list[schemas.PermissionResponse])
async def replace_permissions(
    role_id: UUID,
    request: schemas.RolePermissionAssignRequest,
    http_request: Request,
    replacer_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Replace all permissions for a role (bulk update)."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    try:
        permissions = RoleService.replace_permissions(
            db=db,
            replacer_id=replacer_id,
            tenant_id=tenant_id,
            role_id=role_id,
            permission_ids=request.permission_ids,
            ip=ip,
            user_agent=user_agent,
        )
        return [schemas.PermissionResponse.model_validate(p) for p in permissions]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Permissions Routes
@router.get("/permissions", response_model=schemas.PermissionListResponse)
async def list_permissions(
    module: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(1000, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List permissions with optional module filter."""
    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        tenant_id = UUID(settings.tenant_id)
        require_iam_permission(db, user_id, tenant_id, "system.permissions.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    offset = (page - 1) * per_page
    items, total = PermissionService.list_permissions(
        db=db,
        module_filter=module,
        limit=per_page,
        offset=offset,
    )

    return schemas.PermissionListResponse(
        items=[schemas.PermissionResponse.model_validate(item) for item in items],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/permissions/{permission_id}", response_model=schemas.PermissionResponse)
async def get_permission(
    permission_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get permission details."""
    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        tenant_id = UUID(settings.tenant_id)
        require_iam_permission(db, user_id, tenant_id, "system.permissions.read")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    permission = PermissionService.get_permission(db, permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission {permission_id} not found",
        )

    return schemas.PermissionResponse.model_validate(permission)


# Org Assignments Routes
@router.get("/org-units/{org_unit_id}/assignments", response_model=list[schemas.OrgAssignmentResponse])
async def list_org_unit_assignments(
    org_unit_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List all assignments for an org unit."""
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

    assignments = OrgAssignmentService.list_org_unit_assignments(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
    )

    # Enrich with org unit and role info
    result = []
    for assignment in assignments:
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit
        from sqlalchemy import select

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
            schemas.OrgAssignmentResponse(
                id=assignment.id,
                user_id=assignment.user_id,
                org_unit_id=assignment.org_unit_id,
                role_id=assignment.role_id,
                scope_type=assignment.scope_type,
                org_unit=schemas.OrgUnitInfo.model_validate(org_unit) if org_unit else None,
                role=schemas.RoleInfo.model_validate(role) if role else None,
                custom_org_unit_ids=custom_org_unit_ids,
            )
        )

    return result


# Audit Logs Routes
@router.get("/audit-logs", response_model=schemas.AuditLogListResponse)
async def list_audit_logs(
    actor_id: Optional[UUID] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List audit logs with optional filters and pagination."""
    from datetime import datetime

    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.audit.view")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Parse date strings if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 format.",
            )
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 format.",
            )

    offset = (page - 1) * per_page
    items, total = AuditLogService.list_audit_logs(
        db=db,
        viewer_id=user_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        start_date=start_dt,
        end_date=end_dt,
        limit=per_page,
        offset=offset,
    )

    return schemas.AuditLogListResponse(
        items=[schemas.AuditLogResponse.model_validate(item) for item in items],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/audit-logs/{log_id}", response_model=schemas.AuditLogResponse)
async def get_audit_log(
    log_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get audit log details."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(db, user_id, tenant_id, "system.audit.view")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    log = AuditLogService.get_audit_log(
        db=db,
        viewer_id=user_id,
        tenant_id=tenant_id,
        log_id=log_id,
    )

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log {log_id} not found",
        )

    return schemas.AuditLogResponse.model_validate(log)

