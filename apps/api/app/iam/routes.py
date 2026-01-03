"""IAM API routes for org units, roles, permissions, assignments, and audit logs."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.common.db import get_db
from app.common.request_info import get_request_ip, get_request_user_agent
from app.core.business_metrics import BusinessMetric
from app.core.config import settings
from app.core.metrics_service import MetricsService
from app.iam import schemas
from app.iam.service import (
    AuditLogService,
    OrgAssignmentService,
    OrgUnitService,
    RoleService,
    PermissionService,
)
from app.common.models import OrgUnit, Role

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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ORG_UNIT_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ORG_UNIT_UPDATED,
            tenant_id=tenant_id,
            actor_id=updater_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ORG_UNIT_DELETED,
            tenant_id=tenant_id,
            actor_id=deleter_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ROLE_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ROLE_UPDATED,
            tenant_id=tenant_id,
            actor_id=updater_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.ROLE_DELETED,
            tenant_id=tenant_id,
            actor_id=deleter_id,
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

        # Emit business metric
        MetricsService.emit_iam_metric(
            metric_name=BusinessMetric.PERMISSION_ASSIGNED,
            tenant_id=tenant_id,
            actor_id=assigner_id,
            role_id=str(role_id),
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


# Effective Permissions Endpoint
@router.get("/users/{user_id}/effective-permissions", response_model=schemas.EffectivePermissionsResponse)
async def get_effective_permissions(
    user_id: UUID,
    org_unit_id: UUID = Query(..., description="Org unit ID to check permissions for"),
    viewer_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get effective permissions for a user at a specific org unit."""
    tenant_id = UUID(settings.tenant_id)

    # Check permission
    try:
        from app.iam.scope_validation import require_iam_permission
        require_iam_permission(
            db, viewer_id, tenant_id, "system.users.read"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Get effective permissions
    from app.auth.service import AuthService
    from app.common.models import OrgAssignment
    
    permissions = AuthService.get_effective_permissions_for_org(
        db, user_id, tenant_id, org_unit_id
    )

    # Get applicable assignments for context
    from app.users.scope_validation import _is_descendant
    from app.common.models import OrgAssignmentUnit
    
    stmt = select(OrgAssignment).where(
        OrgAssignment.user_id == user_id,
        OrgAssignment.tenant_id == tenant_id,
    )
    all_assignments = db.execute(stmt).scalars().all()
    
    applicable_assignments = []
    for assn in all_assignments:
        applies = False
        if assn.scope_type == "self" and assn.org_unit_id == org_unit_id:
            applies = True
        elif assn.scope_type == "subtree":
            if _is_descendant(db, org_unit_id, assn.org_unit_id):
                applies = True
        elif assn.scope_type == "custom_set":
            custom_unit = db.execute(
                select(OrgAssignmentUnit).where(
                    OrgAssignmentUnit.assignment_id == assn.id,
                    OrgAssignmentUnit.org_unit_id == org_unit_id,
                )
            ).scalar_one_or_none()
            if custom_unit:
                applies = True
        
        if applies:
            role = db.get(Role, assn.role_id)
            org_unit = db.get(OrgUnit, assn.org_unit_id)
            applicable_assignments.append({
                "assignment_id": str(assn.id),
                "role_id": str(assn.role_id),
                "role_name": role.name if role else None,
                "org_unit_id": str(assn.org_unit_id),
                "org_unit_name": org_unit.name if org_unit else None,
                "scope_type": assn.scope_type,
            })

    return schemas.EffectivePermissionsResponse(
        user_id=user_id,
        org_unit_id=org_unit_id,
        permissions=permissions,
        applicable_assignments=applicable_assignments,
    )


# Bulk Assignment Endpoint
@router.post("/assignments/bulk", response_model=schemas.BulkAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_assignments(
    request: schemas.BulkAssignmentRequest,
    http_request: Request,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create multiple org assignments in bulk."""
    tenant_id = UUID(settings.tenant_id)
    ip = get_request_ip(http_request)
    user_agent = get_request_user_agent(http_request)

    # Convert request to dict format
    assignments_data = []
    for item in request.assignments:
        assignments_data.append({
            "user_id": item.user_id,
            "org_unit_id": item.org_unit_id,
            "role_id": item.role_id,
            "scope_type": item.scope_type,
            "custom_org_unit_ids": item.custom_org_unit_ids,
        })

    try:
        created, failed = OrgAssignmentService.create_bulk_assignments(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            assignments=assignments_data,
            ip=ip,
            user_agent=user_agent,
        )

        # Enrich created assignments with org unit and role info
        from app.common.models import OrgUnit, Role, OrgAssignmentUnit

        created_responses = []
        for assignment in created:
            org_unit = db.get(OrgUnit, assignment.org_unit_id)
            role = db.get(Role, assignment.role_id)

            custom_org_unit_ids = None
            if assignment.scope_type == "custom_set":
                custom_units = db.execute(
                    select(OrgAssignmentUnit).where(
                        OrgAssignmentUnit.assignment_id == assignment.id
                    )
                ).scalars().all()
                custom_org_unit_ids = [unit.org_unit_id for unit in custom_units]

            # Emit business metric for each created assignment
            MetricsService.emit_iam_metric(
                metric_name=BusinessMetric.ASSIGNMENT_CREATED,
                tenant_id=tenant_id,
                actor_id=creator_id,
                user_id=str(assignment.user_id),
                role_id=str(assignment.role_id),
            )

            created_responses.append(
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

        return schemas.BulkAssignmentResponse(
            created=created_responses,
            failed=failed,
            total_requested=len(request.assignments),
            total_created=len(created),
            total_failed=len(failed),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

