"""User provisioning service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.utils import hash_password
from app.common.models import (
    User,
    OrgAssignment,
    OrgAssignmentUnit,
    UserSecret,
    UserInvitation,
    UserInvitationUnit,
    OutboxNotification,
)
from app.users.scope_validation import validate_scope_assignments


class UserProvisioningService:
    @staticmethod
    def create_invitation(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        email: str,
        role_id: UUID,
        org_unit_id: UUID,
        scope_type: str,
        custom_org_unit_ids: Optional[list[UUID]],
        twofa_delivery: str,
    ) -> UserInvitation:
        """Create a user invitation."""
        # Validate creator can create this user
        validate_scope_assignments(
            db, creator_id, tenant_id, org_unit_id, role_id
        )

        # Check if user already exists
        existing = db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if existing:
            # Allow invitation if user exists but has no password (OAuth user)
            if existing.password_hash:
                raise ValueError(
                    f"User with email {email} already exists with password"
                )
            # If no password, allow - invitation will link during activation

        # Check if pending invitation exists
        pending = db.execute(
            select(UserInvitation).where(
                UserInvitation.email == email.lower(),
                UserInvitation.tenant_id == tenant_id,
                UserInvitation.used_at.is_(None),
                UserInvitation.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()
        if pending:
            raise ValueError(
                "Pending invitation already exists for this email"
            )

        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Create invitation
        invitation = UserInvitation(
            tenant_id=tenant_id,
            email=email.lower(),
            token=token,  # Store plain token for email, hash for verification
            token_hash=token_hash,
            invited_by=creator_id,
            role_id=role_id,
            org_unit_id=org_unit_id,
            scope_type=scope_type,
            twofa_delivery=twofa_delivery,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invitation)
        db.flush()

        # Create custom_units if scope_type is custom_set
        if scope_type == "custom_set" and custom_org_unit_ids:
            for custom_org_id in custom_org_unit_ids:
                # Validate creator has access to each custom org
                validate_scope_assignments(
                    db, creator_id, tenant_id, custom_org_id, role_id
                )
                invitation_unit = UserInvitationUnit(
                    invitation_id=invitation.id,
                    org_unit_id=custom_org_id,
                )
                db.add(invitation_unit)

        db.commit()
        db.refresh(invitation)

        # Create outbox notification for email/SMS
        notification = OutboxNotification(
            type="user_invitation",
            payload={
                "invitation_id": str(invitation.id),
                "email": email,
                "token": token,  # Include plain token in notification
                "expires_at": invitation.expires_at.isoformat(),
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Enqueue notification for processing
        from app.jobs.queue import emails_queue
        try:
            emails_queue.enqueue(
                "app.jobs.tasks.process_outbox_notification",
                str(notification.id),
                job_id=str(notification.id),
            )
        except Exception:
            # If queueing fails, notification remains pending and will be
            # picked up by the outbox processor
            pass

        return invitation

    @staticmethod
    def activate_user(
        db: Session,
        token: str,
        password: str,
        tenant_id: UUID,
    ) -> tuple[User, bool]:
        """
        Activate user from invitation token.

        Returns (user, is_new_user).
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        invitation = db.execute(
            select(UserInvitation).where(
                UserInvitation.token_hash == token_hash,
                UserInvitation.used_at.is_(None),
                UserInvitation.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()

        if not invitation:
            raise ValueError("Invalid or expired invitation token")

        # Check if user already exists (maybe via OAuth)
        user = db.execute(
            select(User).where(
                User.email == invitation.email,
                User.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        is_new = False
        if not user:
            # Create new user
            user = User(
                tenant_id=tenant_id,
                email=invitation.email,
                password_hash=hash_password(password),
                is_active=True,
                is_2fa_enabled=False,  # Will be enabled after first 2FA
                created_by=invitation.invited_by,
            )
            db.add(user)
            db.flush()
            is_new = True
        else:
            # Link invitation to existing user (from OAuth)
            if user.password_hash:
                raise ValueError("User already has password set")
            user.password_hash = hash_password(password)
            user.is_active = True

        # Create org assignment
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
            invitation_units = db.execute(
                select(UserInvitationUnit).where(
                    UserInvitationUnit.invitation_id == invitation.id
                )
            ).scalars().all()

            for inv_unit in invitation_units:
                assignment_unit = OrgAssignmentUnit(
                    assignment_id=assignment.id,
                    org_unit_id=inv_unit.org_unit_id,
                )
                db.add(assignment_unit)

        # Create UserSecret for 2FA
        secret = db.execute(
            select(UserSecret).where(UserSecret.user_id == user.id)
        ).scalar_one_or_none()

        if not secret:
            secret = UserSecret(
                user_id=user.id,
                twofa_delivery=invitation.twofa_delivery,
                email=user.email,
            )
            db.add(secret)

        # Mark invitation as used
        invitation.used_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(user)

        return user, is_new

    @staticmethod
    def create_user_direct(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        email: str,
        password: str,
        role_id: UUID,
        org_unit_id: UUID,
        scope_type: str,
        custom_org_unit_ids: Optional[list[UUID]],
        twofa_delivery: str,
    ) -> User:
        """Create user directly (for onsite scenarios)."""
        # Validate creator can create this user
        validate_scope_assignments(
            db, creator_id, tenant_id, org_unit_id, role_id
        )

        # Check if user exists
        existing = db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"User with email {email} already exists")

        # Create user
        user = User(
            tenant_id=tenant_id,
            email=email.lower(),
            password_hash=hash_password(password),
            is_active=True,
            is_2fa_enabled=False,
            created_by=creator_id,
        )
        db.add(user)
        db.flush()

        # Create org assignment
        assignment = OrgAssignment(
            tenant_id=tenant_id,
            user_id=user.id,
            org_unit_id=org_unit_id,
            role_id=role_id,
            scope_type=scope_type,
        )
        db.add(assignment)
        db.flush()

        # Create custom_units if needed
        if scope_type == "custom_set" and custom_org_unit_ids:
            for custom_org_id in custom_org_unit_ids:
                # Validate creator has access to each custom org
                validate_scope_assignments(
                    db, creator_id, tenant_id, custom_org_id, role_id
                )
                assignment_unit = OrgAssignmentUnit(
                    assignment_id=assignment.id,
                    org_unit_id=custom_org_id,
                )
                db.add(assignment_unit)

        # Create UserSecret
        secret = UserSecret(
            user_id=user.id,
            twofa_delivery=twofa_delivery,
            email=user.email,
        )
        db.add(secret)

        db.commit()
        db.refresh(user)

        return user

