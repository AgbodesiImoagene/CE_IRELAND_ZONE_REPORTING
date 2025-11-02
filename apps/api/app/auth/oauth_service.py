from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import (
    User,
    UserIdentity,
    UserInvitation,
    UserInvitationUnit,
    OrgAssignment,
    OrgAssignmentUnit,
)
from app.core.config import settings


class OAuthService:
    """Service for handling OAuth (Google/Facebook) authentication."""

    GOOGLE_CONFIG = {
        "server_metadata_url": (
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        "client_kwargs": {"scope": "openid email profile"},
    }

    FACEBOOK_CONFIG = {
        "server_metadata_url": (
            "https://www.facebook.com/.well-known/openid-configuration"
        ),
        "client_kwargs": {"scope": "email public_profile"},
    }

    @staticmethod
    def find_user_by_email(db: Session, email: str, tenant_id: UUID) -> Optional[User]:
        """Find user by email address."""
        stmt = select(User).where(
            User.email == email.lower(),
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def find_identity(
        db: Session, provider: str, provider_user_id: str
    ) -> Optional[UserIdentity]:
        """Find existing OAuth identity."""
        stmt = select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == provider_user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def link_identity(
        db: Session,
        user_id: UUID,
        provider: str,
        provider_user_id: str,
        email: Optional[str] = None,
        email_verified: bool = False,
    ) -> UserIdentity:
        """Link an OAuth identity to an existing user."""
        existing = OAuthService.find_identity(db, provider, provider_user_id)
        if existing:
            # Update if exists
            if email:
                existing.email = email
            existing.email_verified = email_verified
            return existing

        identity = UserIdentity(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            email_verified=email_verified,
        )
        db.add(identity)
        db.commit()
        db.refresh(identity)
        return identity

    @staticmethod
    def create_user_from_oauth(
        db: Session,
        provider: str,
        provider_user_id: str,
        email: str,
        email_verified: bool = False,
        tenant_id: Optional[UUID] = None,
    ) -> User:
        """Create a new user from OAuth (if signups allowed)."""
        if not tenant_id:
            tenant_id = UUID(settings.tenant_id)

        user = User(
            id=uuid4(),
            tenant_id=tenant_id,
            email=email.lower(),
            password_hash=None,  # No password for SSO users
            is_active=True,
            is_2fa_enabled=False,  # Will be set during 2FA enrollment
        )
        db.add(user)
        db.flush()

        # Link identity
        OAuthService.link_identity(
            db, user.id, provider, provider_user_id, email, email_verified
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def handle_oauth_callback(
        db: Session,
        provider: str,
        provider_user_id: str,
        email: Optional[str],
        email_verified: bool = False,
    ) -> tuple[User, bool]:
        """
        Handle OAuth callback: link identity or create user.

        Returns:
            (User, is_new_user)
        """
        tenant_id = UUID(settings.tenant_id)

        # Check if identity already linked
        identity = OAuthService.find_identity(db, provider, provider_user_id)
        if identity:
            user = db.get(User, identity.user_id)
            if user and user.is_active:
                return user, False

        # Check if user exists by email
        user = None
        if email:
            user = OAuthService.find_user_by_email(db, email, tenant_id)

        if user:
            # Link identity to existing user
            OAuthService.link_identity(
                db, user.id, provider, provider_user_id, email, email_verified
            )

            # Check for pending invitation and auto-activate
            if email:
                OAuthService._check_and_activate_invitation(db, user, email, tenant_id)

            return user, False
        else:
            # NO open signups - require pending invitation
            if not email:
                raise ValueError("Email is required for OAuth authentication")

            # Check for pending invitation first
            invitation = db.execute(
                select(UserInvitation).where(
                    UserInvitation.email == email.lower(),
                    UserInvitation.tenant_id == tenant_id,
                    UserInvitation.used_at.is_(None),
                    UserInvitation.expires_at > datetime.now(timezone.utc),
                )
            ).scalar_one_or_none()

            if not invitation:
                raise ValueError(
                    "No valid invitation found. Please contact your "
                    "administrator or check your invitation email."
                )

            # Create user from OAuth and auto-activate invitation
            user = OAuthService.create_user_from_oauth(
                db,
                provider,
                provider_user_id,
                email,
                email_verified,
                tenant_id,
            )

            # Auto-activate invitation (create org assignment)
            OAuthService._check_and_activate_invitation(db, user, email, tenant_id)

            return user, True

    @staticmethod
    def _check_and_activate_invitation(
        db: Session, user: User, email: str, tenant_id: UUID
    ) -> None:
        """Check for pending invitation and auto-activate if found."""
        invitation = db.execute(
            select(UserInvitation).where(
                UserInvitation.email == email.lower(),
                UserInvitation.tenant_id == tenant_id,
                UserInvitation.used_at.is_(None),
                UserInvitation.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()

        if invitation:
            # Check if user already has this assignment
            existing = db.execute(
                select(OrgAssignment).where(
                    OrgAssignment.user_id == user.id,
                    OrgAssignment.org_unit_id == invitation.org_unit_id,
                    OrgAssignment.role_id == invitation.role_id,
                    OrgAssignment.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not existing:
                # Create org assignment from invitation
                assignment = OrgAssignment(
                    tenant_id=tenant_id,
                    user_id=user.id,
                    org_unit_id=invitation.org_unit_id,
                    role_id=invitation.role_id,
                    scope_type=invitation.scope_type,
                )
                db.add(assignment)
                db.flush()

                # Create custom_units if needed
                if invitation.scope_type == "custom_set":
                    invitation_units = (
                        db.execute(
                            select(UserInvitationUnit).where(
                                UserInvitationUnit.invitation_id == invitation.id
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for inv_unit in invitation_units:
                        assignment_unit = OrgAssignmentUnit(
                            assignment_id=assignment.id,
                            org_unit_id=inv_unit.org_unit_id,
                        )
                        db.add(assignment_unit)

            # Mark invitation as used
            invitation.used_at = datetime.now(timezone.utc)
            db.commit()
