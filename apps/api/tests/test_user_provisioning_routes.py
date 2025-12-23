"""Tests for user provisioning routes (invitations, activation, direct creation)."""

from __future__ import annotations

from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.models import OrgAssignment, OutboxNotification, User, UserInvitation


class TestCreateInvitation:
    def test_create_invitation_success(
        self, client: TestClient, db, admin_token, test_role, test_org_unit
    ):
        """Test successful invitation creation via API."""
        response = client.post(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "invite@example.com",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "invite@example.com"
        assert "id" in data
        assert "expires_at" in data

        # Verify invitation was created in DB
        invitation = db.execute(
            select(UserInvitation).where(UserInvitation.email == "invite@example.com")
        ).scalar_one_or_none()
        assert invitation is not None

    def test_create_invitation_unauthorized(self, client: TestClient):
        """Test invitation creation fails without auth."""
        response = client.post(
            "/api/v1/users/invitations",
            json={
                "email": "invite@example.com",
                "role_id": "00000000-0000-0000-0000-000000000000",
                "org_unit_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 401

    def test_create_invitation_no_permission(
        self, client: TestClient, authenticated_user_token, test_role, test_org_unit
    ):
        """Test invitation creation fails without permission."""
        response = client.post(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            json={
                "email": "invite@example.com",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 400
        assert "system.users.create" in response.json()["detail"].lower()

    def test_create_invitation_invalid_email(
        self, client: TestClient, admin_token, test_role, test_org_unit
    ):
        """Test invitation creation fails with invalid email."""
        response = client.post(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "invalid-email",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 422

    def test_create_invitation_user_exists(
        self,
        client: TestClient,
        admin_token,
        test_role,
        test_org_unit,
        test_user,
    ):
        """Test invitation creation fails if user already exists."""
        response = client.post(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_user.email,
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()


class TestActivateUser:
    def test_activate_user_success(
        self, client: TestClient, db, admin_user, test_role, test_org_unit
    ):
        """Test successful user activation via API."""
        from app.users.service import UserProvisioningService

        # Create invitation first
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="activate@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Activate user
        response = client.post(
            "/api/v1/users/activate",
            json={
                "token": invitation.token,
                "password": "SecurePassword123!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["requires_2fa"] is True
        assert "user_id" in data
        assert "message" in data

        # Verify user was created
        user = db.execute(
            select(User).where(User.email == "activate@example.com")
        ).scalar_one_or_none()
        assert user is not None
        assert user.is_active is True

        # Verify assignment was created
        assignment = db.execute(
            select(OrgAssignment).where(OrgAssignment.user_id == user.id)
        ).scalar_one_or_none()
        assert assignment is not None

    def test_activate_user_invalid_token(self, client: TestClient):
        """Test activation fails with invalid token."""
        response = client.post(
            "/api/v1/users/activate",
            json={
                "token": "invalid_token",
                "password": "SecurePassword123!",
            },
        )
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    def test_activate_user_short_password(
        self, client: TestClient, db, admin_user, test_role, test_org_unit
    ):
        """Test activation fails with short password."""
        from app.users.service import UserProvisioningService

        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="shortpass@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.post(
            "/api/v1/users/activate",
            json={
                "token": invitation.token,
                "password": "short",
            },
        )
        assert response.status_code == 422


class TestCreateUserDirect:
    def test_create_user_direct_success(
        self, client: TestClient, db, admin_token, test_role, test_org_unit
    ):
        """Test successful direct user creation via API."""
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "direct@example.com",
                "password": "TempPassword123!",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "direct@example.com"
        assert data["is_active"] is True
        assert data["requires_2fa"] is True
        assert "user_id" in data

        # Verify user was created
        user = db.execute(
            select(User).where(User.email == "direct@example.com")
        ).scalar_one_or_none()
        assert user is not None

    def test_create_user_direct_unauthorized(self, client: TestClient):
        """Test direct creation fails without auth."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "direct@example.com",
                "password": "TempPassword123!",
                "role_id": "00000000-0000-0000-0000-000000000000",
                "org_unit_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 401

    def test_create_user_direct_no_permission(
        self,
        client: TestClient,
        authenticated_user_token,
        test_role,
        test_org_unit,
    ):
        """Test direct creation fails without permission."""
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            json={
                "email": "direct@example.com",
                "password": "TempPassword123!",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 400
        assert "system.users.create" in response.json()["detail"].lower()

    def test_create_user_direct_user_exists(
        self,
        client: TestClient,
        admin_token,
        test_role,
        test_org_unit,
        test_user,
    ):
        """Test direct creation fails if user already exists."""
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_user.email,
                "password": "TempPassword123!",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_user_direct_invalid_email(
        self, client: TestClient, admin_token, test_role, test_org_unit
    ):
        """Test direct creation fails with invalid email."""
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "invalid-email",
                "password": "TempPassword123!",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 422

    def test_create_user_direct_short_password(
        self, client: TestClient, admin_token, test_role, test_org_unit
    ):
        """Test direct creation fails with short password."""
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "shortpass@example.com",
                "password": "short",
                "role_id": str(test_role.id),
                "org_unit_id": str(test_org_unit.id),
                "scope_type": "self",
                "twofa_delivery": "email",
            },
        )
        assert response.status_code == 422



class TestListInvitations:
    def test_list_invitations_success(
        self, client: TestClient, admin_token, admin_user, test_role, test_org_unit, db
    ):
        """Test listing invitations."""
        from app.users.service import UserProvisioningService
        from uuid import UUID

        # Create an invitation
        UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="list@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.get(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_invitations_with_filters(
        self, client: TestClient, admin_token, admin_user, test_role, test_org_unit, db
    ):
        """Test listing invitations with filters."""
        from app.users.service import UserProvisioningService
        from uuid import UUID

        # Create invitation
        UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="filter@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.get(
            "/api/v1/users/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"email": "filter", "status": "pending"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_invitations_unauthorized(self, client: TestClient):
        """Test listing invitations without auth."""
        response = client.get("/api/v1/users/invitations")
        assert response.status_code == 401


class TestGetInvitation:
    def test_get_invitation_success(
        self, client: TestClient, admin_token, admin_user, test_role, test_org_unit, db
    ):
        """Test getting an invitation."""
        from app.users.service import UserProvisioningService
        from uuid import UUID

        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="get@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.get(
            f"/api/v1/users/invitations/{invitation.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invitation.id)
        assert data["email"] == invitation.email

    def test_get_invitation_not_found(
        self, client: TestClient, admin_token
    ):
        """Test getting non-existent invitation."""
        from uuid import uuid4
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/users/invitations/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestResendInvitation:
    def test_resend_invitation_success(
        self, client: TestClient, admin_token, admin_user, test_role, test_org_unit, db
    ):
        """Test resending an invitation."""
        from app.users.service import UserProvisioningService
        from uuid import UUID

        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="resend@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.post(
            f"/api/v1/users/invitations/{invitation.id}/resend",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invitation.id)

    def test_resend_invitation_not_found(
        self, client: TestClient, admin_token
    ):
        """Test resending non-existent invitation."""
        from uuid import uuid4
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/users/invitations/{fake_id}/resend",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400


class TestCancelInvitation:
    def test_cancel_invitation_success(
        self, client: TestClient, admin_token, admin_user, test_role, test_org_unit, db
    ):
        """Test cancelling an invitation."""
        from app.users.service import UserProvisioningService
        from uuid import UUID

        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="cancel@example.com",
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        response = client.delete(
            f"/api/v1/users/invitations/{invitation.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify cancelled
        from sqlalchemy import select
        from app.common.models import UserInvitation
        cancelled = db.execute(
            select(UserInvitation).where(UserInvitation.id == invitation.id)
        ).scalar_one()
        assert cancelled.used_at is not None

    def test_cancel_invitation_not_found(
        self, client: TestClient, admin_token
    ):
        """Test cancelling non-existent invitation."""
        from uuid import uuid4
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/users/invitations/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400
