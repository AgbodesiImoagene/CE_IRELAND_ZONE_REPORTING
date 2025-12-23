"""Tests for user provisioning service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.auth.utils import hash_password
from app.common.models import (
    OrgAssignment,
    OrgUnit,
    OutboxNotification,
    User,
    UserInvitation,
    UserSecret,
)
from app.users.service import UserManagementService, UserProvisioningService


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


class TestUserManagementService:
    """Tests for UserManagementService."""

    def test_list_users_all(self, db, tenant_id, test_user):
        """Test listing all users."""
        users, total = UserManagementService.list_users(
            db=db,
            tenant_id=UUID(tenant_id),
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any(u.id == test_user.id for u in users)

    def test_list_users_with_filters(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test listing users with filters."""
        # Create a user with assignment
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="filtered@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.flush()

        assignment = OrgAssignment(
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="self",
        )
        db.add(assignment)
        db.commit()

        # Filter by org_unit_id
        users, total = UserManagementService.list_users(
            db=db,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any(u.id == user.id for u in users)

        # Filter by role_id
        users, total = UserManagementService.list_users(
            db=db,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any(u.id == user.id for u in users)

        # Filter by is_active
        users, total = UserManagementService.list_users(
            db=db,
            tenant_id=UUID(tenant_id),
            is_active=True,
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert all(u.is_active is True for u in users)

        # Filter by search
        users, total = UserManagementService.list_users(
            db=db,
            tenant_id=UUID(tenant_id),
            search="filtered",
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any("filtered" in u.email for u in users)

    def test_get_user(self, db, tenant_id, test_user):
        """Test getting a single user."""
        user = UserManagementService.get_user(
            db=db, user_id=test_user.id, tenant_id=UUID(tenant_id)
        )
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_get_user_not_found(self, db, tenant_id):
        """Test getting non-existent user."""
        user = UserManagementService.get_user(
            db=db, user_id=uuid4(), tenant_id=UUID(tenant_id)
        )
        assert user is None

    def test_update_user(self, db, tenant_id, admin_user):
        """Test updating a user."""
        # Create a user to update
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="update@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        updated = UserManagementService.update_user(
            db=db,
            updater_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            email="updated@example.com",
            is_active=False,
            is_2fa_enabled=True,
        )

        assert updated.email == "updated@example.com"
        assert updated.is_active is False
        assert updated.is_2fa_enabled is True

    def test_update_user_partial(self, db, tenant_id, admin_user):
        """Test partial user update."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="partial@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        updated = UserManagementService.update_user(
            db=db,
            updater_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            email="partial_updated@example.com",
        )

        assert updated.email == "partial_updated@example.com"
        assert updated.is_active is True  # Unchanged
        assert updated.is_2fa_enabled is False  # Unchanged

    def test_update_user_no_permission(self, db, tenant_id, test_user):
        """Test update fails without permission."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="noperm@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="User lacks required permission"):
            UserManagementService.update_user(
                db=db,
                updater_id=test_user.id,
                tenant_id=UUID(tenant_id),
                user_id=user.id,
                email="updated@example.com",
            )

    def test_delete_user(self, db, tenant_id, admin_user):
        """Test deleting a user (soft delete)."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="delete@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        UserManagementService.delete_user(
            db=db,
            deleter_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
        )

        db.refresh(user)
        assert user.is_active is False

    def test_disable_user(self, db, tenant_id, admin_user):
        """Test disabling a user."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="disable@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        disabled = UserManagementService.disable_user(
            db=db,
            disabler_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
        )

        assert disabled.is_active is False

    def test_disable_user_already_disabled(self, db, tenant_id, admin_user):
        """Test disabling already disabled user fails."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="alreadydisabled@example.com",
            password_hash=hash_password("password"),
            is_active=False,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="already disabled"):
            UserManagementService.disable_user(
                db=db,
                disabler_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                user_id=user.id,
            )

    def test_enable_user(self, db, tenant_id, admin_user):
        """Test enabling a user."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="enable@example.com",
            password_hash=hash_password("password"),
            is_active=False,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        enabled = UserManagementService.enable_user(
            db=db,
            enabler_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
        )

        assert enabled.is_active is True

    def test_enable_user_already_enabled(self, db, tenant_id, admin_user):
        """Test enabling already enabled user fails."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="alreadyenabled@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="already enabled"):
            UserManagementService.enable_user(
                db=db,
                enabler_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                user_id=user.id,
            )

    def test_reset_password(self, db, tenant_id, admin_user):
        """Test resetting a user's password."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="reset@example.com",
            password_hash=hash_password("oldpassword"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()
        old_hash = user.password_hash

        reset = UserManagementService.reset_password(
            db=db,
            resetter_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            new_password="NewPassword123!",
        )

        assert reset.password_hash != old_hash

    def test_change_password(self, db, tenant_id):
        """Test user changing own password."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="changepass@example.com",
            password_hash=hash_password("oldpassword"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()
        old_hash = user.password_hash

        changed = UserManagementService.change_password(
            db=db,
            user_id=user.id,
            tenant_id=UUID(tenant_id),
            current_password="oldpassword",
            new_password="NewPassword123!",
        )

        assert changed.password_hash != old_hash

    def test_change_password_wrong_current(self, db, tenant_id):
        """Test changing password with wrong current password fails."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="wrongpass@example.com",
            password_hash=hash_password("correctpassword"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="Current password is incorrect"):
            UserManagementService.change_password(
                db=db,
                user_id=user.id,
                tenant_id=UUID(tenant_id),
                current_password="wrongpassword",
                new_password="NewPassword123!",
            )

    def test_change_password_no_password(self, db, tenant_id):
        """Test changing password for user with no password fails."""
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="nopass@example.com",
            password_hash=None,
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="User has no password set"):
            UserManagementService.change_password(
                db=db,
                user_id=user.id,
                tenant_id=UUID(tenant_id),
                current_password="anypassword",
                new_password="NewPassword123!",
            )


class TestInvitationManagement:
    """Tests for invitation management methods in UserProvisioningService."""

    def test_list_invitations_all(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test listing all invitations."""
        # Create an invitation
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="list@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        invitations, total = UserProvisioningService.list_invitations(
            db=db,
            tenant_id=UUID(tenant_id),
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any(inv.id == invitation.id for inv in invitations)

    def test_list_invitations_with_filters(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test listing invitations with filters."""
        # Create invitations
        inv1 = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="filter1@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Filter by email
        invitations, total = UserProvisioningService.list_invitations(
            db=db,
            tenant_id=UUID(tenant_id),
            email="filter1",
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert any("filter1" in inv.email for inv in invitations)

        # Filter by status (pending)
        invitations, total = UserProvisioningService.list_invitations(
            db=db,
            tenant_id=UUID(tenant_id),
            status="pending",
            limit=100,
            offset=0,
        )
        assert total >= 1
        assert all(inv.used_at is None for inv in invitations)

    def test_get_invitation(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test getting a single invitation."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="get@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        retrieved = UserProvisioningService.get_invitation(
            db=db, invitation_id=invitation.id, tenant_id=UUID(tenant_id)
        )
        assert retrieved is not None
        assert retrieved.id == invitation.id
        assert retrieved.email == invitation.email

    def test_get_invitation_not_found(self, db, tenant_id):
        """Test getting non-existent invitation."""
        invitation = UserProvisioningService.get_invitation(
            db=db, invitation_id=uuid4(), tenant_id=UUID(tenant_id)
        )
        assert invitation is None

    def test_resend_invitation(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test resending an invitation."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="resend@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Resend invitation
        resent = UserProvisioningService.resend_invitation(
            db=db,
            resender_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            invitation_id=invitation.id,
        )

        assert resent.id == invitation.id

        # Verify new notification was created
        # Query all user_invitation notifications and filter in Python
        all_notifications = db.execute(
            select(OutboxNotification).where(
                OutboxNotification.type == "user_invitation",
            )
        ).scalars().all()
        # Filter by invitation_id in payload
        notifications = [
            n for n in all_notifications
            if n.payload
            and n.payload.get("invitation_id") == str(invitation.id)
        ]
        assert len(notifications) >= 2  # Original + resend

    def test_resend_invitation_used_fails(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test resending used invitation fails."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="used@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Mark as used
        invitation.used_at = datetime.now(timezone.utc)
        db.commit()

        with pytest.raises(ValueError, match="Cannot resend used invitation"):
            UserProvisioningService.resend_invitation(
                db=db,
                resender_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                invitation_id=invitation.id,
            )

    def test_cancel_invitation(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test cancelling an invitation."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="cancel@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Cancel invitation
        UserProvisioningService.cancel_invitation(
            db=db,
            canceller_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            invitation_id=invitation.id,
        )

        # Verify marked as used
        db.refresh(invitation)
        assert invitation.used_at is not None

    def test_cancel_invitation_already_used_fails(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test cancelling already used invitation fails."""
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="alreadyused@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Mark as used
        invitation.used_at = datetime.now(timezone.utc)
        db.commit()

        with pytest.raises(ValueError, match="already used or cancelled"):
            UserProvisioningService.cancel_invitation(
                db=db,
                canceller_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                invitation_id=invitation.id,
            )
