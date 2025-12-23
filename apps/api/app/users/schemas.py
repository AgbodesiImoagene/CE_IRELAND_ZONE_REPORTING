"""Pydantic schemas for user provisioning."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class InvitationCreateRequest(BaseModel):
    """Request to create a user invitation."""

    email: EmailStr
    role_id: UUID
    org_unit_id: UUID
    scope_type: str = Field(default="self", pattern="^(self|subtree|custom_set)$")
    custom_org_unit_ids: Optional[list[UUID]] = Field(
        default=None
    )  # For custom_set scope
    twofa_delivery: str = Field(default="email", pattern="^(sms|email)$")


class InvitationResponse(BaseModel):
    """Response with invitation details."""

    id: UUID
    email: str
    expires_at: str
    created_at: str


class UserActivationRequest(BaseModel):
    """Request to activate user from invitation token."""

    token: str
    password: str = Field(min_length=12)


class UserActivationResponse(BaseModel):
    """Response after user activation."""

    user_id: UUID
    requires_2fa: bool = True
    message: str


class UserCreateRequest(BaseModel):
    """Request to create user directly (onsite scenarios)."""

    email: EmailStr
    password: str = Field(min_length=12)  # Temporary password
    role_id: UUID
    org_unit_id: UUID
    scope_type: str = Field(default="self", pattern="^(self|subtree|custom_set)$")
    custom_org_unit_ids: Optional[list[UUID]] = Field(default=None)
    twofa_delivery: str = Field(default="email", pattern="^(sms|email)$")


class UserCreateResponse(BaseModel):
    """Response after direct user creation."""

    user_id: UUID
    email: str
    is_active: bool
    requires_2fa: bool = True


# Invitation Management Schemas
class InvitationStatus(str, Enum):
    """Invitation status enum."""

    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"


class InvitationDetailResponse(BaseModel):
    """Response with full invitation details."""

    id: UUID
    email: str
    expires_at: str
    created_at: str
    used_at: Optional[str] = None
    invited_by: UUID
    role_id: UUID
    org_unit_id: UUID
    scope_type: str
    twofa_delivery: str
    status: str  # pending, used, expired


class InvitationListResponse(BaseModel):
    """Paginated list of invitations."""

    items: list[InvitationDetailResponse]
    page: int
    per_page: int
    total: int


# User Management Schemas
class UserResponse(BaseModel):
    """Response with user details."""

    id: UUID
    email: str
    is_active: bool
    is_2fa_enabled: bool
    created_at: str
    updated_at: str
    assignments_count: int = 0  # Number of org assignments


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    page: int
    per_page: int
    total: int


class UserUpdateRequest(BaseModel):
    """Request to update a user."""

    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_2fa_enabled: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    """Request to reset user password (admin action)."""

    new_password: str = Field(..., min_length=12)


class PasswordChangeRequest(BaseModel):
    """Request to change own password."""

    current_password: str
    new_password: str = Field(..., min_length=12)


class PasswordResetResponse(BaseModel):
    """Response after password reset."""

    message: str = "Password reset successfully"
