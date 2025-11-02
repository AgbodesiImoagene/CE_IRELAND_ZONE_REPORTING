"""Pydantic schemas for user provisioning."""

from __future__ import annotations

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
