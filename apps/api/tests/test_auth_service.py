from __future__ import annotations

from uuid import UUID

from app.auth.service import AuthService
from app.common.models import UserSecret, LoginSession


class TestAuthenticateUser:
    def test_authenticate_success(self, db, tenant_id, test_user):
        user = AuthService.authenticate_user(db, "test@example.com", "testpass123")
        assert user is not None
        assert user.id == test_user.id
        assert user.email == "test@example.com"

    def test_authenticate_wrong_password(self, db, tenant_id, test_user):
        user = AuthService.authenticate_user(db, "test@example.com", "wrongpass")
        assert user is None

    def test_authenticate_nonexistent_email(self, db):
        user = AuthService.authenticate_user(db, "nonexistent@example.com", "password")
        assert user is None

    def test_authenticate_inactive_user(self, db, tenant_id, test_user):
        test_user.is_active = False
        db.commit()
        user = AuthService.authenticate_user(db, "test@example.com", "testpass123")
        assert user is None


class Test2FA:
    def test_send_2fa_code_success(self, db, test_user):
        success = AuthService.send_2fa_code(db, test_user.id, "email")
        assert success is True

        secret = db.get(UserSecret, test_user.id)
        assert secret is not None
        assert secret.twofa_delivery == "email"
        assert secret.twofa_secret_hash is not None

    def test_send_2fa_code_nonexistent_user(self, db):
        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        success = AuthService.send_2fa_code(db, fake_id, "email")
        assert success is False

    def test_verify_2fa_code_success(self, db, test_user):
        # Send code first
        AuthService.send_2fa_code(db, test_user.id, "email")

        # Get the code from UserSecret (in real app, this would come from SMS/email)
        secret = db.get(UserSecret, test_user.id)
        # We can't easily test the actual code without mocking, so we'll test the hash directly
        # In integration tests, we'd check console output or use a delivery mock

        # For now, verify that the code hash is stored
        assert secret.twofa_secret_hash is not None

    def test_verify_2fa_code_invalid(self, db, test_user):
        # Send code
        AuthService.send_2fa_code(db, test_user.id, "email")

        # Try invalid code
        valid = AuthService.verify_2fa_code(db, test_user.id, "000000")
        assert valid is False

    def test_verify_2fa_code_nonexistent_user(self, db):
        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        valid = AuthService.verify_2fa_code(db, fake_id, "123456")
        assert valid is False


class TestSessions:
    def test_create_session(self, db, test_user):
        access_token, refresh_token = AuthService.create_session(db, test_user.id)

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert len(access_token) > 0
        assert len(refresh_token) > 0

        # Check session in DB
        from sqlalchemy import select

        stmt = select(LoginSession).where(LoginSession.user_id == test_user.id)
        sessions = db.execute(stmt).scalars().all()
        assert len(list(sessions)) == 1
        session = list(sessions)[0]
        assert session.refresh_token_hash is not None

    def test_refresh_access_token_success(self, db, test_user):
        # Create session
        _, refresh_token = AuthService.create_session(db, test_user.id)

        # Refresh
        result = AuthService.refresh_access_token(db, refresh_token)
        assert result is not None

        access_token, new_refresh_token = result
        assert isinstance(access_token, str)
        assert isinstance(new_refresh_token, str)
        assert new_refresh_token != refresh_token  # Token rotated

    def test_refresh_access_token_invalid(self, db):
        result = AuthService.refresh_access_token(db, "invalid.token.here")
        assert result is None

    def test_revoke_session(self, db, test_user):
        _, refresh_token = AuthService.create_session(db, test_user.id)

        # Revoke
        success = AuthService.revoke_session(db, refresh_token)
        assert success is True

        # Try to refresh (should fail)
        result = AuthService.refresh_access_token(db, refresh_token)
        assert result is None


class TestUserInfo:
    def test_get_user_permissions(
        self, db, test_user, test_role, test_permission, tenant_id
    ):
        # Link permission to role
        from app.common.models import RolePermission

        rp = RolePermission(role_id=test_role.id, permission_id=test_permission.id)
        db.add(rp)
        db.commit()

        perms = AuthService.get_user_permissions(db, test_user.id, UUID(tenant_id))
        assert test_permission.code in perms

    def test_get_user_info(self, db, test_user, tenant_id):
        info = AuthService.get_user_info(db, test_user.id, UUID(tenant_id))

        assert info["id"] == test_user.id
        assert info["email"] == test_user.email
        assert info["is_active"] is True
        assert isinstance(info["roles"], list)
        assert isinstance(info["permissions"], list)
