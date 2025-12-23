"""Tests for IAM API routes."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.common.models import OrgUnit, Role, Permission, RolePermission, OrgAssignment


@pytest.fixture
def iam_user(db, tenant_id, test_org_unit):
    """Create a user with IAM permissions."""
    from app.common.models import User
    from app.auth.utils import hash_password

    # Create IAM permissions
    permissions = [
        Permission(
            id=uuid4(),
            code="system.org_units.read",
            description="Read org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.create",
            description="Create org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.update",
            description="Update org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.delete",
            description="Delete org units",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.read",
            description="Read roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.create",
            description="Create roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.update",
            description="Update roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.delete",
            description="Delete roles",
        ),
        Permission(
            id=uuid4(),
            code="system.permissions.read",
            description="Read permissions",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.assign",
            description="Assign permissions to roles",
        ),
        Permission(
            id=uuid4(),
            code="system.audit.view",
            description="View audit logs",
        ),
    ]

    for perm in permissions:
        db.add(perm)
    db.flush()

    # Create IAM role
    iam_role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="IAM Role",
    )
    db.add(iam_role)
    db.flush()

    # Assign all permissions to role
    for perm in permissions:
        role_perm = RolePermission(
            role_id=iam_role.id,
            permission_id=perm.id,
        )
        db.add(role_perm)

    # Create user
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="iam@example.com",
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
        role_id=iam_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture
def iam_token(iam_user):
    """Return access token for IAM user."""
    from app.auth.utils import create_access_token

    return create_access_token(
        {"sub": str(iam_user.id), "user_id": str(iam_user.id)}
    )


class TestOrgUnitRoutes:
    """Test org unit API routes."""

    def test_list_org_units_success(self, client: TestClient, iam_token, test_org_unit):
        """Test listing org units."""
        response = client.get(
            "/api/v1/iam/org-units",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "page" in data
        assert "total" in data
        assert len(data["items"]) > 0

    def test_list_org_units_with_filters(
        self, client: TestClient, iam_token, test_org_unit
    ):
        """Test listing org units with filters."""
        response = client.get(
            "/api/v1/iam/org-units",
            params={"type": "church", "search": "Test"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_list_org_units_with_pagination(
        self, client: TestClient, iam_token, test_org_unit
    ):
        """Test listing org units with pagination."""
        response = client.get(
            "/api/v1/iam/org-units",
            params={"page": 1, "per_page": 10},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 10

    def test_list_org_units_unauthorized(self, client: TestClient, test_user):
        """Test listing org units without permission."""
        from app.auth.utils import create_access_token

        token = create_access_token(
            {"sub": str(test_user.id), "user_id": str(test_user.id)}
        )

        response = client.get(
            "/api/v1/iam/org-units",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_get_org_unit_success(
        self, client: TestClient, iam_token, test_org_unit
    ):
        """Test getting a single org unit."""
        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_org_unit.id)
        assert data["name"] == test_org_unit.name

    def test_get_org_unit_not_found(self, client: TestClient, iam_token):
        """Test getting non-existent org unit."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/iam/org-units/{fake_id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 404

    def test_create_org_unit_success(
        self, client: TestClient, iam_token, db, tenant_id
    ):
        """Test creating an org unit."""
        response = client.post(
            "/api/v1/iam/org-units",
            json={"name": "New Church", "type": "church"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Church"
        assert data["type"] == "church"

        # Verify it was created
        org_unit = db.query(OrgUnit).filter_by(name="New Church").first()
        assert org_unit is not None

    def test_create_org_unit_with_parent(
        self, client: TestClient, iam_token, test_org_unit, db, tenant_id
    ):
        """Test creating an org unit with parent."""
        # Create a region first
        region = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Region",
            type="region",
        )
        db.add(region)
        db.commit()

        response = client.post(
            "/api/v1/iam/org-units",
            json={"name": "New Zone", "type": "zone", "parent_id": str(region.id)},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Zone"
        assert data["parent_id"] == str(region.id)

    def test_create_org_unit_invalid_type(
        self, client: TestClient, iam_token
    ):
        """Test creating org unit with invalid type."""
        response = client.post(
            "/api/v1/iam/org-units",
            json={"name": "Invalid", "type": "invalid_type"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 422  # Validation error

    def test_update_org_unit_success(
        self, client: TestClient, iam_token, test_org_unit
    ):
        """Test updating an org unit."""
        response = client.patch(
            f"/api/v1/iam/org-units/{test_org_unit.id}",
            json={"name": "Updated Church"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Church"

    def test_delete_org_unit_success(
        self, client: TestClient, iam_token, db, tenant_id
    ):
        """Test deleting an org unit."""
        # Create an org unit to delete
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="To Delete",
            type="church",
        )
        db.add(org_unit)
        db.commit()

        response = client.delete(
            f"/api/v1/iam/org-units/{org_unit.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 204

        # Verify it was deleted
        deleted = db.query(OrgUnit).filter_by(id=org_unit.id).first()
        assert deleted is None

    def test_get_org_unit_children(
        self, client: TestClient, iam_token, test_org_unit, db, tenant_id
    ):
        """Test getting org unit children."""
        # Create a child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child Church",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child)
        db.commit()

        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}/children",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_org_unit_tree(
        self, client: TestClient, iam_token, test_org_unit, db, tenant_id
    ):
        """Test getting org unit subtree."""
        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}/tree",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_org_unit_ancestors(
        self, client: TestClient, iam_token, test_org_unit, db, tenant_id
    ):
        """Test getting org unit ancestors."""
        # Create a parent
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent Region",
            type="region",
        )
        db.add(parent)
        db.flush()

        # Update test_org_unit to have parent
        test_org_unit.parent_id = parent.id
        db.commit()

        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}/ancestors",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRoleRoutes:
    """Test role API routes."""

    def test_list_roles_success(self, client: TestClient, iam_token, test_role):
        """Test listing roles."""
        response = client.get(
            "/api/v1/iam/roles",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_get_role_success(self, client: TestClient, iam_token, test_role):
        """Test getting a single role."""
        response = client.get(
            f"/api/v1/iam/roles/{test_role.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_role.id)
        assert "permissions" in data

    def test_get_role_not_found(self, client: TestClient, iam_token):
        """Test getting non-existent role."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/iam/roles/{fake_id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 404

    def test_create_role_success(self, client: TestClient, iam_token, db, tenant_id):
        """Test creating a role."""
        response = client.post(
            "/api/v1/iam/roles",
            json={"name": "New Role"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Role"
        assert "permissions" in data

        # Verify it was created
        role = db.query(Role).filter_by(name="New Role").first()
        assert role is not None

    def test_update_role_success(self, client: TestClient, iam_token, test_role):
        """Test updating a role."""
        response = client.patch(
            f"/api/v1/iam/roles/{test_role.id}",
            json={"name": "Updated Role"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Role"

    def test_delete_role_success(self, client: TestClient, iam_token, db, tenant_id):
        """Test deleting a role."""
        # Create a role to delete
        role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="To Delete",
        )
        db.add(role)
        db.commit()

        response = client.delete(
            f"/api/v1/iam/roles/{role.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 204

        # Verify it was deleted
        deleted = db.query(Role).filter_by(id=role.id).first()
        assert deleted is None

    def test_get_role_permissions(
        self, client: TestClient, iam_token, test_role, test_permission, db
    ):
        """Test getting role permissions."""
        # Assign permission to role
        role_perm = RolePermission(
            role_id=test_role.id,
            permission_id=test_permission.id,
        )
        db.add(role_perm)
        db.commit()

        response = client.get(
            f"/api/v1/iam/roles/{test_role.id}/permissions",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_assign_permissions(
        self, client: TestClient, iam_token, test_role, test_permission, db
    ):
        """Test assigning permissions to a role."""
        response = client.post(
            f"/api/v1/iam/roles/{test_role.id}/permissions",
            json={"permission_ids": [str(test_permission.id)]},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_remove_permission(
        self, client: TestClient, iam_token, test_role, test_permission, db
    ):
        """Test removing a permission from a role."""
        # Assign permission first
        role_perm = RolePermission(
            role_id=test_role.id,
            permission_id=test_permission.id,
        )
        db.add(role_perm)
        db.commit()

        response = client.delete(
            f"/api/v1/iam/roles/{test_role.id}/permissions/{test_permission.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 204

    def test_replace_permissions(
        self, client: TestClient, iam_token, test_role, db, tenant_id
    ):
        """Test replacing all permissions for a role."""
        # Create permissions
        perm1 = Permission(
            id=uuid4(),
            code="perm1",
            description="Permission 1",
        )
        perm2 = Permission(
            id=uuid4(),
            code="perm2",
            description="Permission 2",
        )
        db.add(perm1)
        db.add(perm2)
        db.commit()

        response = client.put(
            f"/api/v1/iam/roles/{test_role.id}/permissions",
            json={"permission_ids": [str(perm1.id), str(perm2.id)]},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestPermissionRoutes:
    """Test permission API routes."""

    def test_list_permissions_success(
        self, client: TestClient, iam_token, test_permission
    ):
        """Test listing permissions."""
        response = client.get(
            "/api/v1/iam/permissions",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_permissions_with_module_filter(
        self, client: TestClient, iam_token, test_permission
    ):
        """Test listing permissions with module filter."""
        response = client.get(
            "/api/v1/iam/permissions",
            params={"module": "system"},
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_get_permission_success(
        self, client: TestClient, iam_token, test_permission
    ):
        """Test getting a single permission."""
        response = client.get(
            f"/api/v1/iam/permissions/{test_permission.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_permission.id)
        assert data["code"] == test_permission.code

    def test_get_permission_not_found(self, client: TestClient, iam_token):
        """Test getting non-existent permission."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/iam/permissions/{fake_id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )

        assert response.status_code == 404



class TestOrgUnitAssignments:
    def test_list_org_unit_assignments_success(
        self, client: TestClient, iam_user, test_org_unit, db, tenant_id
    ):
        """Test listing assignments for an org unit."""
        from app.auth.utils import create_access_token
        from app.common.models import Permission, RolePermission, Role

        # Add system.users.read permission to iam_user's role
        perm = Permission(
            id=uuid4(),
            code="system.users.read",
            description="Read users",
        )
        db.add(perm)
        db.flush()

        # Get iam_user's role
        from sqlalchemy import select
        assignment = db.execute(
            select(OrgAssignment).where(OrgAssignment.user_id == iam_user.id)
        ).scalar_one()
        role = db.get(Role, assignment.role_id)

        # Assign permission to role
        role_perm = RolePermission(
            role_id=role.id,
            permission_id=perm.id,
        )
        db.add(role_perm)
        db.commit()

        token = create_access_token(
            {"sub": str(iam_user.id), "user_id": str(iam_user.id)}
        )

        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}/assignments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_org_unit_assignments_unauthorized(
        self, client: TestClient, test_org_unit
    ):
        """Test listing assignments without auth."""
        response = client.get(
            f"/api/v1/iam/org-units/{test_org_unit.id}/assignments"
        )
        assert response.status_code == 401
