"""Pydantic schemas for IAM endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# Org Units Schemas
class OrgUnitCreateRequest(BaseModel):
    """Request to create an organizational unit."""

    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(region|zone|group|church|outreach)$")
    parent_id: Optional[UUID] = None


class OrgUnitUpdateRequest(BaseModel):
    """Request to update an organizational unit."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[UUID] = None


class OrgUnitResponse(BaseModel):
    """Response with org unit details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str
    parent_id: Optional[UUID]
    tenant_id: UUID
    created_at: Optional[datetime] = None


class OrgUnitListResponse(BaseModel):
    """Paginated list of org units."""

    items: list[OrgUnitResponse]
    page: int
    per_page: int
    total: int


# Roles Schemas
class RoleCreateRequest(BaseModel):
    """Request to create a role."""

    name: str = Field(..., min_length=1, max_length=100)


class RoleUpdateRequest(BaseModel):
    """Request to update a role."""

    name: str = Field(..., min_length=1, max_length=100)


class PermissionResponse(BaseModel):
    """Response with permission details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: Optional[str]


class RoleResponse(BaseModel):
    """Response with role details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    tenant_id: UUID
    permissions: list[PermissionResponse]
    created_at: Optional[datetime] = None


class RoleListResponse(BaseModel):
    """Paginated list of roles."""

    items: list[RoleResponse]
    page: int
    per_page: int
    total: int


class RolePermissionAssignRequest(BaseModel):
    """Request to assign permissions to a role."""

    permission_ids: list[UUID] = Field(..., min_length=1)


# Permissions Schemas
class PermissionListResponse(BaseModel):
    """Paginated list of permissions."""

    items: list[PermissionResponse]
    page: int
    per_page: int
    total: int


# Org Assignments Schemas
class OrgAssignmentCreateRequest(BaseModel):
    """Request to create an org assignment."""

    org_unit_id: UUID
    role_id: UUID
    scope_type: str = Field(
        default="self", pattern="^(self|subtree|custom_set)$"
    )
    custom_org_unit_ids: Optional[list[UUID]] = None


class OrgAssignmentUpdateRequest(BaseModel):
    """Request to update an org assignment."""

    role_id: Optional[UUID] = None
    scope_type: Optional[str] = Field(
        None, pattern="^(self|subtree|custom_set)$"
    )
    custom_org_unit_ids: Optional[list[UUID]] = None


class CustomUnitAddRequest(BaseModel):
    """Request to add an org unit to custom_set scope."""

    org_unit_id: UUID


class OrgAssignmentUnitRequest(BaseModel):
    """Request to add an org unit to custom_set scope (alias for compatibility)."""

    org_unit_id: UUID


class OrgUnitInfo(BaseModel):
    """Org unit info for assignment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str


class RoleInfo(BaseModel):
    """Role info for assignment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class OrgAssignmentResponse(BaseModel):
    """Response with org assignment details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    org_unit_id: UUID
    role_id: UUID
    scope_type: str
    org_unit: Optional[OrgUnitInfo] = None
    role: Optional[RoleInfo] = None
    custom_org_unit_ids: Optional[list[UUID]] = None


class OrgAssignmentListResponse(BaseModel):
    """Paginated list of org assignments."""

    items: list[OrgAssignmentResponse]
    page: int
    per_page: int
    total: int


# Audit Logs Schemas
class AuditLogResponse(BaseModel):
    """Response with audit log details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    actor_id: Optional[UUID]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    before_json: Optional[dict]
    after_json: Optional[dict]
    ip: Optional[str]
    user_agent: Optional[str]
    occurred_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse]
    page: int
    per_page: int
    total: int
