"""Tests for user management routes (list, get, update, delete, disable, enable, password)."""

from __future__ import annotations

from uuid import UUID, uuid4
from fastapi.testclient import TestClient
import pytest

from app.common.models import OrgAssignment, User


@pytest.fixture
def user_mgmt_user(db, tenant_id, test_org_unit):
    """Create a user with user management permissions."""
    from app.common.models import Role, Permission, RolePermission
    from app.auth.utils import hash_password

    # Create user management permissions
    permissions = [
        Permission(
            id=uuid4(),
            code="system.users.read",
            description="Read users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.update",
            description="Update users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.disable",
            description="Disable/enable users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.reset_password",
            description="Reset user passwords",
        ),
    ]

    for perm in permissions:
        db.add(perm)
    db.flush()

    # Create user management role
    user_mgmt_role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="User Management Role",
    )
    db.add(user_mgmt_role)
    db.flush()

    # Assign all permissions to role
    for perm in permissions:
        role_perm = RolePermission(
            role_id=user_mgmt_role.id,
            permission_id=perm.id,
        )
        db.add(role_perm)

    # Create user
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="usermgmt@example.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
        is_2fa_enabled=False,
    )
    db.add(user)
    db.flush()

    # Assign role to user
    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=user_mgmt_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    # Create token
    from app.auth.utils import create_access_token
    token = create_access_token(
        {"sub": str(user.id), "user_id": str(user.id)}
    )

    return user, token


class TestListUsers:
    def test_list_users_success(self, client: TestClient, user_mgmt_user):
        """Test listing users."""
        user, token = user_mgmt_user
        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data

    def test_list_users_with_filters(
        self, client: TestClient, user_mgmt_user, test_org_unit, test_role
    ):
        """Test listing users with filters."""
        user, token = user_mgmt_user
        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "is_active": True,
                "search": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_users_unauthorized(self, client: TestClient):
        """Test listing users without auth."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401

    def test_list_users_no_permission(
        self, client: TestClient, authenticated_user_token
    ):
        """Test listing users without permission."""
        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
        )
        assert response.status_code == 403


class TestGetUser:
    def test_get_user_success(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test getting a user."""
        user, token = user_mgmt_user
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email

    def test_get_user_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test getting non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/users/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_get_user_unauthorized(self, client: TestClient, test_user):
        """Test getting user without auth."""
        response = client.get(f"/api/v1/users/{test_user.id}")
        assert response.status_code == 401


class TestUpdateUser:
    def test_update_user_success(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test updating a user."""
        user, token = user_mgmt_user
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "updated@example.com",
                "is_active": False,
                "is_2fa_enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["is_active"] is False
        assert data["is_2fa_enabled"] is True

    def test_update_user_partial(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test partial user update."""
        user, token = user_mgmt_user
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "partial@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "partial@example.com"

    def test_update_user_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test updating non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.patch(
            f"/api/v1/users/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "updated@example.com"},
        )
        assert response.status_code == 400

    def test_update_user_unauthorized(self, client: TestClient, test_user):
        """Test updating user without auth."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"email": "updated@example.com"},
        )
        assert response.status_code == 401


class TestDeleteUser:
    def test_delete_user_success(
        self, client: TestClient, user_mgmt_user, db, tenant_id
    ):
        """Test deleting a user."""
        from app.auth.utils import hash_password

        # Create a user to delete
        user_to_delete = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="todelete@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user_to_delete)
        db.commit()

        user, token = user_mgmt_user
        response = client.delete(
            f"/api/v1/users/{user_to_delete.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        # Verify soft delete
        db.refresh(user_to_delete)
        assert user_to_delete.is_active is False

    def test_delete_user_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test deleting non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/users/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestDisableUser:
    def test_disable_user_success(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test disabling a user."""
        user, token = user_mgmt_user
        response = client.post(
            f"/api/v1/users/{test_user.id}/disable",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_disable_user_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test disabling non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/users/{fake_id}/disable",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestEnableUser:
    def test_enable_user_success(
        self, client: TestClient, user_mgmt_user, db, tenant_id
    ):
        """Test enabling a user."""
        from app.auth.utils import hash_password

        # Create a disabled user
        disabled_user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="disabled@example.com",
            password_hash=hash_password("password"),
            is_active=False,
            is_2fa_enabled=False,
        )
        db.add(disabled_user)
        db.commit()

        user, token = user_mgmt_user
        response = client.post(
            f"/api/v1/users/{disabled_user.id}/enable",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_enable_user_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test enabling non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/users/{fake_id}/enable",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestResetPassword:
    def test_reset_password_success(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test resetting a user's password."""
        user, token = user_mgmt_user
        response = client.post(
            f"/api/v1/users/{test_user.id}/reset-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "NewPassword123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_reset_password_not_found(
        self, client: TestClient, user_mgmt_user
    ):
        """Test resetting password for non-existent user."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/users/{fake_id}/reset-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "NewPassword123!"},
        )
        assert response.status_code == 400


class TestChangePassword:
    def test_change_password_success(
        self, client: TestClient, test_user
    ):
        """Test user changing own password."""
        from app.auth.utils import create_access_token

        token = create_access_token(
            {"sub": str(test_user.id), "user_id": str(test_user.id)}
        )

        response = client.post(
            f"/api/v1/users/{test_user.id}/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "testpass123",
                "new_password": "NewPassword123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_change_password_wrong_current(
        self, client: TestClient, test_user
    ):
        """Test changing password with wrong current password."""
        from app.auth.utils import create_access_token

        token = create_access_token(
            {"sub": str(test_user.id), "user_id": str(test_user.id)}
        )

        response = client.post(
            f"/api/v1/users/{test_user.id}/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "wrongpassword",
                "new_password": "NewPassword123!",
            },
        )
        assert response.status_code == 400

    def test_change_password_different_user(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test changing password for different user fails."""
        user, token = user_mgmt_user
        response = client.post(
            f"/api/v1/users/{test_user.id}/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "testpass123",
                "new_password": "NewPassword123!",
            },
        )
        assert response.status_code == 403
