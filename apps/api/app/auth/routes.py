from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    TwoFASendRequest,
    TwoFAVerifyRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserInfoResponse,
)
from app.auth.service import AuthService
from app.auth.dependencies import get_current_user
from app.common.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return LoginResponse(requires_2fa=True, user_id=user.id)


@router.post("/2fa/send")
async def send_2fa_code(request: TwoFASendRequest, db: Session = Depends(get_db)):
    if request.delivery_method not in ["sms", "email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delivery_method must be 'sms' or 'email'",
        )

    success = AuthService.send_2fa_code(db, request.user_id, request.delivery_method)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"message": "2FA code sent"}


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(request: TwoFAVerifyRequest, db: Session = Depends(get_db)):
    valid = AuthService.verify_2fa_code(db, request.user_id, request.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired 2FA code",
        )

    access_token, refresh_token = AuthService.create_session(db, request.user_id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    result = AuthService.refresh_access_token(db, request.refresh_token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token, refresh_token = result
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
async def logout(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    AuthService.revoke_session(db, request.refresh_token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user_info: dict = Depends(get_current_user)):
    """Get current user information with RLS enforced."""
    return UserInfoResponse(**user_info)
