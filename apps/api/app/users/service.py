"""User provisioning service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.auth.utils import hash_password, verify_password
from app.common.audit import create_audit_log
from app.common.models import (
    User,
    OrgAssignment,
    OrgAssignmentUnit,
    UserSecret,
    UserInvitation,
    UserInvitationUnit,
    OutboxNotification,
)
from app.iam.scope_validation import require_iam_permission
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
        validate_scope_assignments(db, creator_id, tenant_id, org_unit_id, role_id)

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
            raise ValueError("Pending invitation already exists for this email")

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
        validate_scope_assignments(db, creator_id, tenant_id, org_unit_id, role_id)

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

    @staticmethod
    def list_invitations(
        db: Session,
        tenant_id: UUID,
        email: Optional[str] = None,
        status: Optional[str] = None,
        expires_before: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[UserInvitation], int]:
        """List invitations with optional filters and pagination."""
        stmt = select(UserInvitation).where(
            UserInvitation.tenant_id == tenant_id
        )

        if email:
            stmt = stmt.where(UserInvitation.email.ilike(f"%{email}%"))

        if status:
            now = datetime.now(timezone.utc)
            if status == "pending":
                stmt = stmt.where(
                    UserInvitation.used_at.is_(None),
                    UserInvitation.expires_at > now,
                )
            elif status == "used":
                stmt = stmt.where(UserInvitation.used_at.isnot(None))
            elif status == "expired":
                stmt = stmt.where(
                    UserInvitation.expires_at <= now,
                    UserInvitation.used_at.is_(None),
                )

        if expires_before:
            stmt = stmt.where(UserInvitation.expires_at < expires_before)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination and ordering
        stmt = (
            stmt.order_by(UserInvitation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_invitation(
        db: Session, invitation_id: UUID, tenant_id: UUID
    ) -> Optional[UserInvitation]:
        """Get a single invitation by ID."""
        return db.execute(
            select(UserInvitation).where(
                UserInvitation.id == invitation_id,
                UserInvitation.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def resend_invitation(
        db: Session,
        resender_id: UUID,
        tenant_id: UUID,
        invitation_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserInvitation:
        """Resend an invitation email."""
        require_iam_permission(
            db, resender_id, tenant_id, "system.users.create"
        )

        invitation = UserProvisioningService.get_invitation(
            db, invitation_id, tenant_id
        )
        if not invitation:
            raise ValueError(f"Invitation {invitation_id} not found")

        if invitation.used_at is not None:
            raise ValueError("Cannot resend used invitation")

        # Ensure timezone-aware comparison
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            # If naive, assume UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ValueError("Cannot resend expired invitation")

        # Create new outbox notification
        notification = OutboxNotification(
            type="user_invitation",
            payload={
                "invitation_id": str(invitation.id),
                "email": invitation.email,
                "token": invitation.token,  # Use same token
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
            # If queueing fails, notification remains pending
            pass

        # Create audit log
        create_audit_log(
            db,
            resender_id,
            "resend_invitation",
            "user_invitations",
            invitation_id,
            None,
            {"email": invitation.email},
            ip=ip,
            user_agent=user_agent,
        )

        return invitation

    @staticmethod
    def cancel_invitation(
        db: Session,
        canceller_id: UUID,
        tenant_id: UUID,
        invitation_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Cancel an invitation (mark as used to prevent activation)."""
        require_iam_permission(
            db, canceller_id, tenant_id, "system.users.create"
        )

        invitation = UserProvisioningService.get_invitation(
            db, invitation_id, tenant_id
        )
        if not invitation:
            raise ValueError(f"Invitation {invitation_id} not found")

        if invitation.used_at is not None:
            raise ValueError("Invitation already used or cancelled")

        before_json = {
            "email": invitation.email,
            "used_at": None,
        }

        # Mark as used (cancelled)
        invitation.used_at = datetime.now(timezone.utc)

        after_json = {
            "email": invitation.email,
            "used_at": invitation.used_at.isoformat(),
        }

        # Create audit log
        create_audit_log(
            db,
            canceller_id,
            "cancel_invitation",
            "user_invitations",
            invitation_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()


class UserManagementService:
    """Service for managing users."""

    @staticmethod
    def list_users(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        role_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        """List users with optional filters and pagination."""
        # Build base query
        stmt = select(User).where(User.tenant_id == tenant_id)

        # Apply filters
        if org_unit_id or role_id:
            # Join with OrgAssignment for filtering
            stmt = stmt.join(OrgAssignment, OrgAssignment.user_id == User.id)
            if org_unit_id:
                stmt = stmt.where(OrgAssignment.org_unit_id == org_unit_id)
            if role_id:
                stmt = stmt.where(OrgAssignment.role_id == role_id)

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(User.email.ilike(search_pattern))

        # Count total (before pagination)
        if org_unit_id or role_id:
            # For filtered queries with joins, count distinct users
            count_stmt = (
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(OrgAssignment, OrgAssignment.user_id == User.id)
                .where(User.tenant_id == tenant_id)
            )
            if org_unit_id:
                count_stmt = count_stmt.where(OrgAssignment.org_unit_id == org_unit_id)
            if role_id:
                count_stmt = count_stmt.where(OrgAssignment.role_id == role_id)
            if is_active is not None:
                count_stmt = count_stmt.where(User.is_active == is_active)
            if search:
                search_pattern = f"%{search}%"
                count_stmt = count_stmt.where(User.email.ilike(search_pattern))
        else:
            # Simple count without joins
            count_stmt = select(func.count(User.id)).where(User.tenant_id == tenant_id)
            if is_active is not None:
                count_stmt = count_stmt.where(User.is_active == is_active)
            if search:
                search_pattern = f"%{search}%"
                count_stmt = count_stmt.where(User.email.ilike(search_pattern))

        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination and ordering
        stmt = stmt.distinct().order_by(User.email).limit(limit).offset(offset)

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_user(
        db: Session, user_id: UUID, tenant_id: UUID
    ) -> Optional[User]:
        """Get a single user by ID."""
        return db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def update_user(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_2fa_enabled: Optional[bool] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Update a user."""
        require_iam_permission(db, updater_id, tenant_id, "system.users.update")

        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Track changes for audit log
        before_json = {
            "email": user.email,
            "is_active": user.is_active,
            "is_2fa_enabled": user.is_2fa_enabled,
        }

        # Update email if provided
        if email is not None:
            email_lower = email.lower()
            # Check for duplicate email
            existing = db.execute(
                select(User).where(
                    User.email == email_lower,
                    User.tenant_id == tenant_id,
                    User.id != user_id,
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError(f"User with email {email} already exists")
            user.email = email_lower

        # Update is_active if provided
        if is_active is not None:
            user.is_active = is_active

        # Update is_2fa_enabled if provided
        if is_2fa_enabled is not None:
            user.is_2fa_enabled = is_2fa_enabled

        user.updated_at = datetime.now(timezone.utc)

        after_json = {
            "email": user.email,
            "is_active": user.is_active,
            "is_2fa_enabled": user.is_2fa_enabled,
        }

        # Create audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Delete a user (soft delete - sets is_active=False)."""
        require_iam_permission(db, deleter_id, tenant_id, "system.users.update")

        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        before_json = {
            "email": user.email,
            "is_active": user.is_active,
        }

        # Soft delete
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        after_json = {
            "email": user.email,
            "is_active": False,
        }

        # Create audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()

    @staticmethod
    def disable_user(
        db: Session,
        disabler_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Disable a user account."""
        require_iam_permission(
            db, disabler_id, tenant_id, "system.users.disable"
        )

        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if not user.is_active:
            raise ValueError("User is already disabled")

        before_json = {"is_active": True}
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        after_json = {"is_active": False}

        # Create audit log
        create_audit_log(
            db,
            disabler_id,
            "disable",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def enable_user(
        db: Session,
        enabler_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Enable a user account."""
        require_iam_permission(
            db, enabler_id, tenant_id, "system.users.disable"
        )

        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.is_active:
            raise ValueError("User is already enabled")

        before_json = {"is_active": False}
        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)
        after_json = {"is_active": True}

        # Create audit log
        create_audit_log(
            db,
            enabler_id,
            "enable",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reset_password(
        db: Session,
        resetter_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        new_password: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Reset a user's password (admin action)."""
        require_iam_permission(
            db, resetter_id, tenant_id, "system.users.reset_password"
        )

        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        before_json = {"password_reset": True}
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        after_json = {"password_reset": True}

        # Create audit log
        create_audit_log(
            db,
            resetter_id,
            "reset_password",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(
        db: Session,
        user_id: UUID,
        tenant_id: UUID,
        current_password: str,
        new_password: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Change user's own password (requires current password)."""
        user = UserManagementService.get_user(db, user_id, tenant_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if not user.password_hash:
            raise ValueError("User has no password set")

        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        before_json = {"password_change": True}
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        after_json = {"password_change": True}

        # Create audit log
        create_audit_log(
            db,
            user_id,
            "change_password",
            "users",
            user_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(user)
        return user
