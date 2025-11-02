from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.auth.oauth_service import OAuthService
from app.auth.oauth_state import (
    generate_and_store_state,
    validate_and_consume_state,
)
from app.auth.schemas import LoginResponse
from app.common.db import get_db
from app.core.config import settings

router = APIRouter(prefix="/oauth", tags=["oauth"])


def get_oauth_client(provider: str) -> AsyncOAuth2Client:
    """Get OAuth client for provider."""
    if provider == "google":
        if not settings.google_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth not configured",
            )
        return AsyncOAuth2Client(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
        )
    elif provider == "facebook":
        if not settings.facebook_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Facebook OAuth not configured",
            )
        return AsyncOAuth2Client(
            client_id=settings.facebook_client_id,
            client_secret=settings.facebook_client_secret,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )


@router.get("/{provider}/start")
async def oauth_start(
    provider: str,
    request: Request,
):
    """Initiate OAuth flow - redirect to provider."""
    client = get_oauth_client(provider)
    redirect_uri = request.url_for("oauth_callback", provider=provider)

    # Generate and store state token in Redis for CSRF protection
    state = await generate_and_store_state(provider)

    # Generate authorization URL with our state
    if provider == "google":
        auth_url, _ = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            redirect_uri=redirect_uri,
            scope="openid email profile",
            state=state,  # Use our generated state
        )
    else:  # facebook
        auth_url, _ = client.create_authorization_url(
            "https://www.facebook.com/v18.0/dialog/oauth",
            redirect_uri=redirect_uri,
            scope="email public_profile",
            state=state,  # Use our generated state
        )

    return RedirectResponse(url=auth_url)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle OAuth callback - exchange code for user info."""
    # Validate state parameter for CSRF protection
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state parameter",
        )

    is_valid_state = await validate_and_consume_state(provider, state)
    if not is_valid_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    try:
        client = get_oauth_client(provider)
        redirect_uri = request.url_for("oauth_callback", provider=provider)

        # Exchange code for token
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
        else:  # facebook
            token_url = "https://graph.facebook.com/v18.0/oauth/access_token"

        token = await client.fetch_token(
            token_url,
            authorization_response=request.url,
            redirect_uri=redirect_uri,
        )

        access_token = token.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not retrieve access token",
            )

        # Get user info from provider
        if provider == "google":
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            async with client:
                resp = await client.get(user_info_url)
                user_info = resp.json()
                provider_user_id = str(user_info.get("id") or user_info.get("sub", ""))
                email = (
                    user_info.get("email", "").lower()
                    if user_info.get("email")
                    else None
                )
                email_verified = user_info.get("verified_email", False)
        else:  # facebook
            user_info_url = "https://graph.facebook.com/me?fields=id,email,name"
            async with client:
                resp = await client.get(user_info_url)
                user_info = resp.json()
                provider_user_id = str(user_info.get("id", ""))
                email = (
                    user_info.get("email", "").lower()
                    if user_info.get("email")
                    else None
                )
                email_verified = bool(email)  # Facebook doesn't provide verification

        if not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not retrieve user ID from provider",
            )

        # Handle OAuth callback - link identity or create user
        try:
            user, _ = OAuthService.handle_oauth_callback(
                db,
                provider,
                provider_user_id,
                email,
                email_verified,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        # Still require 2FA even for SSO users
        return LoginResponse(
            requires_2fa=True,
            user_id=user.id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}",
        ) from e
