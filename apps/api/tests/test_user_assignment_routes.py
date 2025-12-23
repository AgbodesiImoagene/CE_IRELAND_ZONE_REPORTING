"""Tests for user assignment routes (list, create, update, delete, custom units)."""

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
            code="system.users.create",
            description="Create users",
        ),
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
        Permission(
            id=uuid4(),
            code="system.users.assign",
            description="Assign org scopes",
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


class TestListUserAssignments:
    def test_list_user_assignments_success(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test listing assignments for a user."""
        user, token = user_mgmt_user
        response = client.get(
            f"/api/v1/users/{test_user.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_user_assignments_unauthorized(
        self, client: TestClient, test_user
    ):
        """Test listing assignments without auth."""
        response = client.get(f"/api/v1/users/{test_user.id}/assignments")
        assert response.status_code == 401


class TestCreateAssignment:
    def test_create_assignment_success(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test creating an assignment."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        existing = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.commit()

        user, token = user_mgmt_user
        response = client.post(
            f"/api/v1/users/{test_user.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "scope_type": "self",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(test_user.id)
        assert data["org_unit_id"] == str(test_org_unit.id)
        assert data["role_id"] == str(test_role.id)

    def test_create_assignment_custom_set(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test creating assignment with custom_set scope."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        existing = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.commit()

        from app.common.models import OrgUnit

        # Create another org unit
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give user_mgmt_user access to custom_org
        user, token = user_mgmt_user
        from app.common.models import OrgAssignment
        from sqlalchemy import select
        # Get the role_id from user's existing assignment
        user_assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()
        user_mgmt_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=custom_org.id,
            role_id=user_assignment.role_id,
            scope_type="self",
        )
        db.add(user_mgmt_assignment)
        db.commit()

        response = client.post(
            f"/api/v1/users/{test_user.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "scope_type": "custom_set",
                "custom_org_unit_ids": [str(custom_org.id)],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scope_type"] == "custom_set"
        assert custom_org.id in [UUID(uid) for uid in data["custom_org_unit_ids"]]

    def test_create_assignment_unauthorized(
        self, client: TestClient, test_user, test_role, test_org_unit
    ):
        """Test creating assignment without auth."""
        response = client.post(
            f"/api/v1/users/{test_user.id}/assignments",
            json={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "scope_type": "self",
            },
        )
        assert response.status_code == 401


class TestUpdateAssignment:
    def test_update_assignment_success(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test updating an assignment."""
        from app.common.models import Role
        from sqlalchemy import select
        from app.common.models import OrgAssignment

        # Use existing assignment from fixture
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()
        assignment_id = assignment.id

        # Create new role
        new_role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="New Role",
        )
        db.add(new_role)
        db.commit()

        # Update assignment
        user, token = user_mgmt_user
        response = client.patch(
            f"/api/v1/users/{test_user.id}/assignments/{assignment_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"role_id": str(new_role.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role_id"] == str(new_role.id)

    def test_update_assignment_not_found(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test updating non-existent assignment."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.patch(
            f"/api/v1/users/{test_user.id}/assignments/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope_type": "subtree"},
        )
        assert response.status_code == 400


class TestDeleteAssignment:
    def test_delete_assignment_success(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test deleting an assignment."""
        # Use existing assignment from fixture
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()
        assignment_id = assignment.id

        # Delete assignment
        user, token = user_mgmt_user
        response = client.delete(
            f"/api/v1/users/{test_user.id}/assignments/{assignment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

    def test_delete_assignment_not_found(
        self, client: TestClient, user_mgmt_user, test_user
    ):
        """Test deleting non-existent assignment."""
        user, token = user_mgmt_user
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/users/{test_user.id}/assignments/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestCustomUnits:
    def test_add_custom_unit_success(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test adding custom unit to assignment."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        existing = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.commit()

        from app.common.models import OrgUnit

        # Create assignment with custom_set scope
        user, token = user_mgmt_user
        create_response = client.post(
            f"/api/v1/users/{test_user.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "scope_type": "custom_set",
            },
        )
        assignment_id = create_response.json()["id"]

        # Create another org unit
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org 2",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give user_mgmt_user access to custom_org
        from app.common.models import OrgAssignment
        from sqlalchemy import select
        # Get the role_id from user's existing assignment
        user_assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()
        user_mgmt_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=custom_org.id,
            role_id=user_assignment.role_id,
            scope_type="self",
        )
        db.add(user_mgmt_assignment)
        db.commit()

        # Add custom unit
        response = client.post(
            f"/api/v1/users/{test_user.id}/assignments/{assignment_id}/units",
            headers={"Authorization": f"Bearer {token}"},
            json={"org_unit_id": str(custom_org.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert custom_org.id in [UUID(uid) for uid in data["custom_org_unit_ids"]]

    def test_remove_custom_unit_success(
        self, client: TestClient, user_mgmt_user, test_user, test_role, test_org_unit, db, tenant_id
    ):
        """Test removing custom unit from assignment."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        existing = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.commit()

        from app.common.models import OrgUnit

        # Create another org unit
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org 3",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give user_mgmt_user access to custom_org
        user, token = user_mgmt_user
        from app.common.models import OrgAssignment
        user_assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()
        user_mgmt_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=custom_org.id,
            role_id=user_assignment.role_id,
            scope_type="self",
        )
        db.add(user_mgmt_assignment)
        db.commit()

        # Create assignment with custom_set scope and custom unit
        create_response = client.post(
            f"/api/v1/users/{test_user.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "role_id": str(test_role.id),
                "scope_type": "custom_set",
                "custom_org_unit_ids": [str(custom_org.id)],
            },
        )
        assignment_id = create_response.json()["id"]

        # Remove custom unit
        response = client.delete(
            f"/api/v1/users/{test_user.id}/assignments/{assignment_id}/units/{custom_org.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

