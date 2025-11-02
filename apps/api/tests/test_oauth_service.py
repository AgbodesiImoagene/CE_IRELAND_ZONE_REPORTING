from __future__ import annotations

import pytest
from uuid import UUID

from app.auth.oauth_service import OAuthService
from app.common.models import UserIdentity


class TestFindUserByEmail:
    def test_find_existing_user(self, db, tenant_id, test_user):
        user = OAuthService.find_user_by_email(db, "test@example.com", UUID(tenant_id))
        assert user is not None
        assert user.id == test_user.id
        assert user.email == "test@example.com"

    def test_find_nonexistent_user(self, db, tenant_id):
        user = OAuthService.find_user_by_email(
            db, "nonexistent@example.com", UUID(tenant_id)
        )
        assert user is None

    def test_find_inactive_user(self, db, tenant_id, test_user):
        test_user.is_active = False
        db.commit()

        user = OAuthService.find_user_by_email(db, "test@example.com", UUID(tenant_id))
        assert user is None


class TestFindIdentity:
    def test_find_existing_identity(self, db, test_user):
        from uuid import uuid4

        identity = UserIdentity(
            id=uuid4(),
            user_id=test_user.id,
            provider="google",
            provider_user_id="google123",
            email="test@example.com",
            email_verified=True,
        )
        db.add(identity)
        db.commit()

        found = OAuthService.find_identity(db, "google", "google123")
        assert found is not None
        assert found.user_id == test_user.id

    def test_find_nonexistent_identity(self, db):
        found = OAuthService.find_identity(db, "google", "nonexistent")
        assert found is None


class TestLinkIdentity:
    def test_link_new_identity(self, db, test_user):
        identity = OAuthService.link_identity(
            db,
            test_user.id,
            "google",
            "google123",
            email="test@example.com",
            email_verified=True,
        )

        assert identity is not None
        assert identity.user_id == test_user.id
        assert identity.provider == "google"
        assert identity.provider_user_id == "google123"

    def test_link_existing_identity_updates(self, db, test_user):
        # Create existing identity
        identity = OAuthService.link_identity(
            db, test_user.id, "google", "google123", email="old@example.com"
        )

        # Link again with new email
        updated = OAuthService.link_identity(
            db,
            test_user.id,
            "google",
            "google123",
            email="new@example.com",
            email_verified=True,
        )

        assert updated.id == identity.id
        assert updated.email == "new@example.com"
        assert updated.email_verified is True


class TestCreateUserFromOAuth:
    def test_create_new_user(self, db, tenant_id):
        user = OAuthService.create_user_from_oauth(
            db,
            "google",
            "google456",
            "newuser@example.com",
            email_verified=True,
            tenant_id=UUID(tenant_id),
        )

        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.password_hash is None
        assert user.is_active is True
        assert user.is_2fa_enabled is False

        # Check identity was linked
        identity = OAuthService.find_identity(db, "google", "google456")
        assert identity is not None
        assert identity.user_id == user.id


class TestHandleOAuthCallback:
    def test_callback_existing_identity(self, db, test_user):
        # Create existing identity
        OAuthService.link_identity(
            db, test_user.id, "google", "google789", email="test@example.com"
        )

        user, is_new = OAuthService.handle_oauth_callback(
            db, "google", "google789", "test@example.com", True
        )

        assert user.id == test_user.id
        assert is_new is False

    def test_callback_existing_user_by_email(self, db, tenant_id, test_user):
        # No identity, but user exists by email
        user, is_new = OAuthService.handle_oauth_callback(
            db,
            "facebook",
            "fb123",
            "test@example.com",
            False,
        )

        assert user.id == test_user.id
        assert is_new is False

        # Identity should be linked now
        identity = OAuthService.find_identity(db, "facebook", "fb123")
        assert identity is not None
        assert identity.user_id == test_user.id

    def test_callback_create_new_user_with_invitation(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test OAuth signup succeeds when invitation exists."""
        from app.users.service import UserProvisioningService

        # Create invitation first
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email="brandnew@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Now OAuth should work
        user, is_new = OAuthService.handle_oauth_callback(
            db,
            "google",
            "google999",
            "brandnew@example.com",
            True,
        )

        assert user is not None
        assert user.email == "brandnew@example.com"
        assert is_new is True

        # Check invitation was auto-activated
        db.refresh(invitation)
        assert invitation.used_at is not None

    def test_callback_create_new_user_no_invitation(self, db, tenant_id):
        """Test OAuth signup fails without invitation."""
        with pytest.raises(ValueError, match="No valid invitation found"):
            OAuthService.handle_oauth_callback(
                db,
                "google",
                "google999",
                "brandnew@example.com",
                True,
            )

    def test_callback_no_email_error(self, db):
        # Should raise ValueError if no email for new user
        try:
            OAuthService.handle_oauth_callback(
                db, "google", "google_no_email", None, False
            )
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected
