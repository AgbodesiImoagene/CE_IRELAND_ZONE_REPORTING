"""Tests for user provisioning service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    OrgAssignment,
    OrgUnit,
    OutboxNotification,
    User,
    UserInvitation,
    UserSecret,
)
from app.users.service import UserProvisioningService


def _ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TestCreateInvitation:
    def test_create_invitation_success(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test successful invitation creation."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="newuser@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        assert invitation is not None
        assert invitation.email == "newuser@example.com"
        assert invitation.token is not None
        assert invitation.token_hash is not None
        assert invitation.invited_by == admin_user.id
        assert invitation.role_id == test_role.id
        assert invitation.org_unit_id == test_org_unit.id
        # Ensure timezone-aware comparison
        assert _ensure_timezone_aware(invitation.expires_at) > datetime.now(
            timezone.utc
        )

        # Check outbox notification was created
        notification = db.execute(
            select(OutboxNotification).where(
                OutboxNotification.type == "user_invitation"
            )
        ).scalar_one_or_none()
        assert notification is not None
        assert notification.payload["email"] == "newuser@example.com"
        assert notification.payload["token"] == invitation.token

    def test_create_invitation_no_permission(
        self, db, tenant_id, test_user, test_role, test_org_unit
    ):
        """Test invitation creation fails without permission."""
        with pytest.raises(ValueError, match="User lacks system.users.create"):
            UserProvisioningService.create_invitation(
                db=db,
                creator_id=test_user.id,
                tenant_id=UUID(tenant_id),
                email="newuser@example.com",
                role_id=test_role.id,
                org_unit_id=test_org_unit.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )

    def test_create_invitation_no_org_access(
        self, db, tenant_id, admin_user, test_role
    ):  # noqa: E501
        """Test invitation creation fails without org access."""
        # Create org unit that admin_user doesn't have access to
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other Org",
            type="church",
            parent_id=None,
        )
        db.add(other_org)
        db.commit()

        with pytest.raises(ValueError, match="does not have access to org unit"):
            UserProvisioningService.create_invitation(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                email="newuser@example.com",
                role_id=test_role.id,
                org_unit_id=other_org.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )

    def test_create_invitation_user_exists_with_password(
        self,
        db,
        tenant_id,
        admin_user,
        test_role,
        test_org_unit,
        test_user,
    ):  # noqa: E501
        """Test invitation creation fails if user already exists with password."""
        with pytest.raises(ValueError, match="already exists with password"):
            UserProvisioningService.create_invitation(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                email=test_user.email,
                role_id=test_role.id,
                org_unit_id=test_org_unit.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )

    def test_create_invitation_oauth_user_allowed(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test invitation creation allowed for OAuth users (no password)."""
        # Create OAuth user (no password)
        oauth_user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="oauth_invite@example.com",
            password_hash=None,  # OAuth user
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(oauth_user)
        db.commit()

        # Should succeed - invitation allowed for OAuth users
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="oauth_invite@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        assert invitation is not None
        assert invitation.email == "oauth_invite@example.com"

    def test_create_invitation_pending_exists(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test invitation creation fails if pending invitation exists."""
        # Create first invitation
        UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="pending@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Try to create another for same email
        with pytest.raises(ValueError, match="Pending invitation already exists"):
            UserProvisioningService.create_invitation(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                email="pending@example.com",
                role_id=test_role.id,
                org_unit_id=test_org_unit.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )


class TestActivateUser:
    def test_activate_user_success(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test successful user activation from invitation."""
        # Create invitation
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="activate@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Activate user
        user, is_new = UserProvisioningService.activate_user(
            db=db,
            token=invitation.token,
            password="SecurePassword123!",
            tenant_id=UUID(tenant_id),
        )

        assert user is not None
        assert is_new is True
        assert user.email == "activate@example.com"
        assert user.password_hash is not None
        assert user.is_active is True
        assert user.is_2fa_enabled is False

        # Check assignment was created
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.role_id == test_role.id,
            )
        ).scalar_one_or_none()
        assert assignment is not None
        assert assignment.org_unit_id == test_org_unit.id

        # Check UserSecret was created
        secret = db.get(UserSecret, user.id)
        assert secret is not None
        assert secret.twofa_delivery == "email"

        # Check invitation was marked as used
        db.refresh(invitation)
        assert invitation.used_at is not None

    def test_activate_user_invalid_token(self, db, tenant_id):
        """Test activation fails with invalid token."""
        with pytest.raises(ValueError, match="Invalid or expired"):
            UserProvisioningService.activate_user(
                db=db,
                token="invalid_token",
                password="SecurePassword123!",
                tenant_id=UUID(tenant_id),
            )

    def test_activate_user_expired_invitation(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test activation fails with expired invitation."""
        # Create invitation and manually expire it
        invitation = UserInvitation(
            tenant_id=UUID(tenant_id),
            email="expired@example.com",
            token="expired_token",
            token_hash="expired_hash",
            invited_by=admin_user.id,
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            twofa_delivery="email",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(invitation)
        db.commit()

        with pytest.raises(ValueError, match="Invalid or expired"):
            UserProvisioningService.activate_user(
                db=db,
                token="expired_token",
                password="SecurePassword123!",
                tenant_id=UUID(tenant_id),
            )

    def test_activate_user_existing_oauth_user(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):  # noqa: E501
        """Test activation links to existing OAuth user."""
        # Create OAuth user (no password)
        oauth_user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="oauth@example.com",
            password_hash=None,
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(oauth_user)
        db.commit()

        # Create invitation (should now work for OAuth users)
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="oauth@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Activate (should link to existing user)
        user, is_new = UserProvisioningService.activate_user(
            db=db,
            token=invitation.token,
            password="SecurePassword123!",
            tenant_id=UUID(tenant_id),
        )

        assert user.id == oauth_user.id
        assert is_new is False
        assert user.password_hash is not None

    def test_activate_user_already_has_password(
        self, db, tenant_id, admin_user, test_role, test_org_unit, test_user
    ):
        """Test activation fails if user already has password."""
        # Create invitation for existing user
        token = "existing_token"
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        invitation = UserInvitation(
            tenant_id=UUID(tenant_id),
            email=test_user.email,
            token=token,
            token_hash=token_hash,
            invited_by=admin_user.id,
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            twofa_delivery="email",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invitation)
        db.commit()

        with pytest.raises(ValueError, match="already has password set"):
            UserProvisioningService.activate_user(
                db=db,
                token=token,
                password="SecurePassword123!",
                tenant_id=UUID(tenant_id),
            )


class TestCreateUserDirect:
    def test_create_user_direct_success(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test successful direct user creation."""
        user = UserProvisioningService.create_user_direct(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="direct@example.com",
            password="TempPassword123!",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        assert user is not None
        assert user.email == "direct@example.com"
        assert user.password_hash is not None
        assert user.is_active is True
        assert user.created_by == admin_user.id

        # Check assignment was created
        assignment = db.execute(
            select(OrgAssignment).where(OrgAssignment.user_id == user.id)
        ).scalar_one_or_none()
        assert assignment is not None

        # Check UserSecret was created
        secret = db.get(UserSecret, user.id)
        assert secret is not None

    def test_create_user_direct_no_permission(
        self, db, tenant_id, test_user, test_role, test_org_unit
    ):
        """Test direct creation fails without permission."""
        with pytest.raises(ValueError, match="User lacks system.users.create"):
            UserProvisioningService.create_user_direct(
                db=db,
                creator_id=test_user.id,
                tenant_id=UUID(tenant_id),
                email="direct@example.com",
                password="TempPassword123!",
                role_id=test_role.id,
                org_unit_id=test_org_unit.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )

    def test_create_user_direct_user_exists(
        self, db, tenant_id, admin_user, test_role, test_org_unit, test_user
    ):
        """Test direct creation fails if user already exists."""
        with pytest.raises(ValueError, match="already exists"):
            UserProvisioningService.create_user_direct(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                email=test_user.email,
                password="TempPassword123!",
                role_id=test_role.id,
                org_unit_id=test_org_unit.id,
                scope_type="self",
                custom_org_unit_ids=None,
                twofa_delivery="email",
            )
