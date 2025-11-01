from __future__ import annotations

from pydantic import BaseModel, EmailStr
from uuid import UUID


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    requires_2fa: bool
    user_id: UUID | None = None


class TwoFASendRequest(BaseModel):
    user_id: UUID
    delivery_method: str  # "sms" or "email"


class TwoFAVerifyRequest(BaseModel):
    user_id: UUID
    code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserInfoResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_2fa_enabled: bool
    roles: list[dict]
    permissions: list[str]
    org_assignments: list[dict] | None = None
