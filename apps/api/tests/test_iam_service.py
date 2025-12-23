"""Tests for IAM service layer."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import (
    OrgUnit,
    Role,
    Permission,
    RolePermission,
    OrgAssignment,
    OrgAssignmentUnit,
    User,
)
from app.iam.service import (
    AuditLogService,
    OrgAssignmentService,
    OrgUnitService,
    RoleService,
    PermissionService,
)


@pytest.fixture
def iam_user_with_permissions(db, tenant_id, test_org_unit):
    """Create a user with IAM permissions for service tests."""
    from app.common.models import User
    from app.auth.utils import hash_password

    # Create permissions
    perms = [
        Permission(id=uuid4(), code="system.org_units.create", description="Create"),
        Permission(id=uuid4(), code="system.org_units.update", description="Update"),
        Permission(id=uuid4(), code="system.org_units.delete", description="Delete"),
        Permission(id=uuid4(), code="system.roles.create", description="Create"),
        Permission(id=uuid4(), code="system.roles.update", description="Update"),
        Permission(id=uuid4(), code="system.roles.delete", description="Delete"),
        Permission(id=uuid4(), code="system.roles.assign", description="Assign"),
    ]

    for perm in perms:
        db.add(perm)
    db.flush()

    # Create role
    role = Role(id=uuid4(), tenant_id=UUID(tenant_id), name="IAM Admin")
    db.add(role)
    db.flush()

    # Assign permissions
    for perm in perms:
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    # Create user
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="iam_admin@example.com",
        password_hash=hash_password("test"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Assign role
    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    return user


class TestOrgUnitService:
    """Test OrgUnitService business logic."""

    def test_list_org_units(self, db: Session, tenant_id: str, test_org_unit):
        """Test listing org units."""
        items, total = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id)
        )

        assert isinstance(items, list)
        assert total >= 1
        assert any(ou.id == test_org_unit.id for ou in items)

    def test_list_org_units_with_type_filter(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test listing org units with type filter."""
        items, total = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id), type_filter="church"
        )

        assert all(ou.type == "church" for ou in items)

    def test_list_org_units_with_search(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test listing org units with search."""
        items, total = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id), search="Test"
        )

        assert all("Test" in ou.name for ou in items)

    def test_list_org_units_with_pagination(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test listing org units with pagination."""
        items1, total1 = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id), limit=1, offset=0
        )
        items2, total2 = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id), limit=1, offset=1
        )

        assert total1 == total2
        assert len(items1) <= 1
        assert len(items2) <= 1
        if items1 and items2:
            assert items1[0].id != items2[0].id

    def test_get_org_unit(self, db: Session, tenant_id: str, test_org_unit):
        """Test getting a single org unit."""
        org_unit = OrgUnitService.get_org_unit(
            db=db, org_unit_id=test_org_unit.id, tenant_id=UUID(tenant_id)
        )

        assert org_unit is not None
        assert org_unit.id == test_org_unit.id
        assert org_unit.name == test_org_unit.name

    def test_get_org_unit_not_found(self, db: Session, tenant_id: str):
        """Test getting non-existent org unit."""
        fake_id = uuid4()
        org_unit = OrgUnitService.get_org_unit(
            db=db, org_unit_id=fake_id, tenant_id=UUID(tenant_id)
        )

        assert org_unit is None

    def test_create_org_unit_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test creating an org unit."""
        org_unit = OrgUnitService.create_org_unit(
            db=db,
            creator_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            name="New Church",
            type="church",
        )

        assert org_unit is not None
        assert org_unit.name == "New Church"
        assert org_unit.type == "church"

    def test_create_org_unit_with_parent(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test creating org unit with parent."""
        # Create parent
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent Region",
            type="region",
        )
        db.add(parent)
        db.commit()

        org_unit = OrgUnitService.create_org_unit(
            db=db,
            creator_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            name="Child Zone",
            type="zone",
            parent_id=parent.id,
        )

        assert org_unit.parent_id == parent.id

    def test_create_org_unit_invalid_hierarchy(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test creating org unit with invalid hierarchy."""
        # Create child first
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child Church",
            type="church",
        )
        db.add(child)
        db.commit()

        # Try to create parent under child (should fail)
        with pytest.raises(ValueError, match="hierarchy"):
            OrgUnitService.create_org_unit(
                db=db,
                creator_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                name="Parent Region",
                type="region",
                parent_id=child.id,
            )

    def test_create_org_unit_duplicate_name(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit
    ):
        """Test creating org unit with duplicate name."""
        with pytest.raises(ValueError, match="already exists"):
            OrgUnitService.create_org_unit(
                db=db,
                creator_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                name=test_org_unit.name,
                type="church",
                parent_id=test_org_unit.parent_id,
            )

    def test_update_org_unit_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit
    ):
        """Test updating an org unit."""
        updated = OrgUnitService.update_org_unit(
            db=db,
            updater_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Updated Name",
        )

        assert updated.name == "Updated Name"

    def test_update_org_unit_not_found(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test updating non-existent org unit."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="not found"):
            OrgUnitService.update_org_unit(
                db=db,
                updater_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=fake_id,
                name="New Name",
            )

    def test_update_org_unit_circular_reference(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit
    ):
        """Test updating org unit to be its own parent."""
        with pytest.raises(ValueError, match="own parent"):
            OrgUnitService.update_org_unit(
                db=db,
                updater_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                parent_id=test_org_unit.id,
            )

    def test_delete_org_unit_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test deleting an org unit."""
        # Create org unit to delete
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="To Delete",
            type="church",
        )
        db.add(org_unit)
        db.commit()

        OrgUnitService.delete_org_unit(
            db=db,
            deleter_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
        )

        # Verify deleted
        deleted = db.query(OrgUnit).filter_by(id=org_unit.id).first()
        assert deleted is None

    def test_delete_org_unit_with_children(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit
    ):
        """Test deleting org unit with children fails."""
        # Create child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child)
        db.commit()

        with pytest.raises(ValueError, match="children"):
            OrgUnitService.delete_org_unit(
                db=db,
                deleter_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
            )

    def test_get_children(self, db: Session, tenant_id: str, test_org_unit):
        """Test getting org unit children."""
        # Create children
        child1 = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child 1",
            type="church",
            parent_id=test_org_unit.id,
        )
        child2 = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child 2",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child1)
        db.add(child2)
        db.commit()

        children = OrgUnitService.get_children(
            db=db, org_unit_id=test_org_unit.id, tenant_id=UUID(tenant_id)
        )

        assert len(children) == 2
        assert {c.id for c in children} == {child1.id, child2.id}

    def test_get_subtree(self, db: Session, tenant_id: str, test_org_unit):
        """Test getting org unit subtree."""
        # Create nested children
        child1 = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child 1",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child1)
        db.flush()

        grandchild = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Grandchild",
            type="church",
            parent_id=child1.id,
        )
        db.add(grandchild)
        db.commit()

        subtree = OrgUnitService.get_subtree(
            db=db, org_unit_id=test_org_unit.id, tenant_id=UUID(tenant_id)
        )

        assert len(subtree) >= 2
        assert any(ou.id == child1.id for ou in subtree)
        assert any(ou.id == grandchild.id for ou in subtree)

    def test_get_ancestors(self, db: Session, tenant_id: str, test_org_unit):
        """Test getting org unit ancestors."""
        # Create parent hierarchy
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent",
            type="region",
        )
        db.add(parent)
        db.flush()

        test_org_unit.parent_id = parent.id
        db.commit()

        ancestors = OrgUnitService.get_ancestors(
            db=db, org_unit_id=test_org_unit.id, tenant_id=UUID(tenant_id)
        )

        assert len(ancestors) == 1
        assert ancestors[0].id == parent.id

    def test_get_ancestors_no_parent(self, db: Session, tenant_id: str, test_org_unit):
        """Test getting ancestors for org unit with no parent."""
        ancestors = OrgUnitService.get_ancestors(
            db=db, org_unit_id=test_org_unit.id, tenant_id=UUID(tenant_id)
        )

        assert ancestors == []

    def test_get_ancestors_not_found(self, db: Session, tenant_id: str):
        """Test getting ancestors for non-existent org unit."""
        fake_id = uuid4()
        ancestors = OrgUnitService.get_ancestors(
            db=db, org_unit_id=fake_id, tenant_id=UUID(tenant_id)
        )

        assert ancestors == []

    def test_update_org_unit_parent_to_descendant(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit
    ):
        """Test updating org unit parent to a descendant fails."""
        # Create child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child)
        db.commit()

        # Try to set parent to child (should fail)
        with pytest.raises(ValueError, match="descendant"):
            OrgUnitService.update_org_unit(
                db=db,
                updater_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                parent_id=child.id,
            )

    def test_delete_org_unit_with_assignments(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_org_unit, test_user
    ):
        """Test deleting org unit with user assignments fails."""
        # test_user is already assigned to test_org_unit
        with pytest.raises(ValueError, match="assignments"):
            OrgUnitService.delete_org_unit(
                db=db,
                deleter_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
            )

    def test_list_org_units_with_parent_filter(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test listing org units with parent filter."""
        # Create child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child",
            type="church",
            parent_id=test_org_unit.id,
        )
        db.add(child)
        db.commit()

        items, total = OrgUnitService.list_org_units(
            db=db, tenant_id=UUID(tenant_id), parent_id=test_org_unit.id
        )

        assert len(items) >= 1
        assert all(ou.parent_id == test_org_unit.id for ou in items)


class TestRoleService:
    """Test RoleService business logic."""

    def test_list_roles(self, db: Session, tenant_id: str, test_role):
        """Test listing roles."""
        items, total = RoleService.list_roles(db=db, tenant_id=UUID(tenant_id))

        assert isinstance(items, list)
        assert total >= 1
        assert any(r.id == test_role.id for r in items)

    def test_get_role(self, db: Session, tenant_id: str, test_role):
        """Test getting a single role."""
        role = RoleService.get_role(
            db=db, role_id=test_role.id, tenant_id=UUID(tenant_id)
        )

        assert role is not None
        assert role.id == test_role.id

    def test_create_role_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test creating a role."""
        role = RoleService.create_role(
            db=db,
            creator_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            name="New Role",
        )

        assert role is not None
        assert role.name == "New Role"

    def test_create_role_duplicate_name(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role
    ):
        """Test creating role with duplicate name."""
        with pytest.raises(ValueError, match="already exists"):
            RoleService.create_role(
                db=db,
                creator_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                name=test_role.name,
            )

    def test_update_role_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role
    ):
        """Test updating a role."""
        updated = RoleService.update_role(
            db=db,
            updater_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            name="Updated Role",
        )

        assert updated.name == "Updated Role"

    def test_delete_role_success(
        self, db: Session, tenant_id: str, iam_user_with_permissions
    ):
        """Test deleting a role."""
        # Create role to delete
        role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="To Delete",
        )
        db.add(role)
        db.commit()

        RoleService.delete_role(
            db=db,
            deleter_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=role.id,
        )

        # Verify deleted
        deleted = db.query(Role).filter_by(id=role.id).first()
        assert deleted is None

    def test_delete_role_with_assignments(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role, test_user
    ):
        """Test deleting role with assignments fails."""
        # Role is already assigned to test_user
        with pytest.raises(ValueError, match="assigned"):
            RoleService.delete_role(
                db=db,
                deleter_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                role_id=test_role.id,
            )

    def test_get_role_permissions(
        self, db: Session, tenant_id: str, test_role, test_permission
    ):
        """Test getting role permissions."""
        # Assign permission
        role_perm = RolePermission(
            role_id=test_role.id,
            permission_id=test_permission.id,
        )
        db.add(role_perm)
        db.commit()

        permissions = RoleService.get_role_permissions(
            db=db, role_id=test_role.id, tenant_id=UUID(tenant_id)
        )

        assert len(permissions) >= 1
        assert any(p.id == test_permission.id for p in permissions)

    def test_assign_permissions(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role, test_permission
    ):
        """Test assigning permissions to a role."""
        permissions = RoleService.assign_permissions(
            db=db,
            assigner_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            permission_ids=[test_permission.id],
        )

        assert len(permissions) >= 1
        assert any(p.id == test_permission.id for p in permissions)

    def test_assign_permissions_invalid(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role
    ):
        """Test assigning invalid permissions."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="not found"):
            RoleService.assign_permissions(
                db=db,
                assigner_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                role_id=test_role.id,
                permission_ids=[fake_id],
            )

    def test_remove_permission(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role, test_permission
    ):
        """Test removing a permission from a role."""
        # Assign first
        role_perm = RolePermission(
            role_id=test_role.id,
            permission_id=test_permission.id,
        )
        db.add(role_perm)
        db.commit()

        RoleService.remove_permission(
            db=db,
            remover_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            permission_id=test_permission.id,
        )

        # Verify removed
        remaining = db.query(RolePermission).filter_by(
            role_id=test_role.id, permission_id=test_permission.id
        ).first()
        assert remaining is None

    def test_replace_permissions(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role
    ):
        """Test replacing all permissions for a role."""
        # Create permissions
        perm1 = Permission(id=uuid4(), code="perm1", description="Perm 1")
        perm2 = Permission(id=uuid4(), code="perm2", description="Perm 2")
        db.add(perm1)
        db.add(perm2)
        db.commit()

        permissions = RoleService.replace_permissions(
            db=db,
            replacer_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            permission_ids=[perm1.id, perm2.id],
        )

        assert len(permissions) == 2
        assert {p.id for p in permissions} == {perm1.id, perm2.id}

    def test_remove_permission_not_assigned(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role, test_permission
    ):
        """Test removing a permission that's not assigned."""
        with pytest.raises(ValueError, match="not assigned"):
            RoleService.remove_permission(
                db=db,
                remover_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                role_id=test_role.id,
                permission_id=test_permission.id,
            )

    def test_remove_permission_invalid_permission(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role
    ):
        """Test removing invalid permission."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="not found"):
            RoleService.remove_permission(
                db=db,
                remover_id=iam_user_with_permissions.id,
                tenant_id=UUID(tenant_id),
                role_id=test_role.id,
                permission_id=fake_id,
            )

    def test_replace_permissions_removes_existing(
        self, db: Session, tenant_id: str, iam_user_with_permissions, test_role, test_permission
    ):
        """Test that replace_permissions removes existing permissions."""
        # Assign permission first
        role_perm = RolePermission(
            role_id=test_role.id,
            permission_id=test_permission.id,
        )
        db.add(role_perm)
        db.commit()

        # Create new permission
        new_perm = Permission(id=uuid4(), code="new_perm", description="New")
        db.add(new_perm)
        db.commit()

        # Replace with new permission only
        permissions = RoleService.replace_permissions(
            db=db,
            replacer_id=iam_user_with_permissions.id,
            tenant_id=UUID(tenant_id),
            role_id=test_role.id,
            permission_ids=[new_perm.id],
        )

        # Should only have new permission
        assert len(permissions) == 1
        assert permissions[0].id == new_perm.id


class TestPermissionService:
    """Test PermissionService business logic."""

    def test_list_permissions(self, db: Session, test_permission):
        """Test listing permissions."""
        items, total = PermissionService.list_permissions(db=db)

        assert isinstance(items, list)
        assert total >= 1
        assert any(p.id == test_permission.id for p in items)

    def test_list_permissions_with_module_filter(
        self, db: Session, test_permission
    ):
        """Test listing permissions with module filter."""
        items, total = PermissionService.list_permissions(
            db=db, module_filter="test"
        )

        assert all("test" in p.code for p in items)

    def test_get_permission(self, db: Session, test_permission):
        """Test getting a single permission."""
        permission = PermissionService.get_permission(
            db=db, permission_id=test_permission.id
        )

        assert permission is not None
        assert permission.id == test_permission.id

    def test_get_permission_not_found(self, db: Session):
        """Test getting non-existent permission."""
        fake_id = uuid4()
        permission = PermissionService.get_permission(
            db=db, permission_id=fake_id
        )

        assert permission is None


class TestOrgAssignmentService:
    """Test OrgAssignmentService business logic."""

    def test_list_user_assignments(
        self, db: Session, tenant_id: str, test_user, test_role, test_org_unit
    ):
        """Test listing assignments for a user."""
        assignments = OrgAssignmentService.list_user_assignments(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )
        assert len(assignments) >= 1
        assert any(a.user_id == test_user.id for a in assignments)

    def test_list_org_unit_assignments(
        self, db: Session, tenant_id: str, test_user, test_role, test_org_unit
    ):
        """Test listing assignments for an org unit."""
        assignments = OrgAssignmentService.list_org_unit_assignments(
            db=db,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
        )
        assert len(assignments) >= 1
        assert any(a.org_unit_id == test_org_unit.id for a in assignments)

    def test_create_assignment_self_scope(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
    ):
        """Test creating assignment with self scope."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
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

        assignment = OrgAssignmentService.create_assignment(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="self",
        )

        assert assignment is not None
        assert assignment.user_id == test_user.id
        assert assignment.org_unit_id == test_org_unit.id
        assert assignment.role_id == test_role.id
        assert assignment.scope_type == "self"

    def test_create_assignment_custom_set(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
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

        # Create another org unit for custom set
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give admin_user access to custom_org
        from app.common.models import OrgAssignment
        admin_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=admin_user.id,
            org_unit_id=custom_org.id,
            role_id=test_role.id,
            scope_type="self",
        )
        db.add(admin_assignment)
        db.commit()

        assignment = OrgAssignmentService.create_assignment(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="custom_set",
            custom_org_unit_ids=[custom_org.id],
        )

        assert assignment is not None
        assert assignment.scope_type == "custom_set"

        # Verify custom unit was created
        custom_unit = db.execute(
            select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assignment.id,
                OrgAssignmentUnit.org_unit_id == custom_org.id,
            )
        ).scalar_one_or_none()
        assert custom_unit is not None

    def test_create_assignment_duplicate(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
    ):
        """Test creating duplicate assignment fails."""
        # Delete existing assignment from fixture
        from sqlalchemy import select
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

        # Create first assignment
        OrgAssignmentService.create_assignment(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="self",
        )

        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            OrgAssignmentService.create_assignment(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                user_id=test_user.id,
                org_unit_id=test_org_unit.id,
                role_id=test_role.id,
                scope_type="self",
            )

    def test_update_assignment(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
    ):
        """Test updating an assignment."""
        # Use existing assignment from fixture
        from sqlalchemy import select
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()

        # Create new role
        new_role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="New Role",
        )
        db.add(new_role)
        db.commit()

        # Update assignment
        updated = OrgAssignmentService.update_assignment(
            db=db,
            updater_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            assignment_id=assignment.id,
            role_id=new_role.id,
        )

        assert updated.role_id == new_role.id

    def test_delete_assignment(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
    ):
        """Test deleting an assignment."""
        # Use existing assignment from fixture
        from sqlalchemy import select
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.org_unit_id == test_org_unit.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one()

        # Delete assignment
        OrgAssignmentService.delete_assignment(
            db=db,
            deleter_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            assignment_id=assignment.id,
        )

        # Verify deleted
        deleted = db.get(OrgAssignment, assignment.id)
        assert deleted is None

    def test_add_custom_unit(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
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

        # Create assignment with custom_set scope
        assignment = OrgAssignmentService.create_assignment(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="custom_set",
        )

        # Create another org unit
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org 2",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give admin_user access to custom_org
        from app.common.models import OrgAssignment
        admin_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=admin_user.id,
            org_unit_id=custom_org.id,
            role_id=test_role.id,
            scope_type="self",
        )
        db.add(admin_assignment)
        db.commit()

        # Add custom unit
        custom_unit = OrgAssignmentService.add_custom_unit(
            db=db,
            adder_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            assignment_id=assignment.id,
            org_unit_id=custom_org.id,
        )

        assert custom_unit is not None
        assert custom_unit.org_unit_id == custom_org.id

    def test_remove_custom_unit(
        self,
        db: Session,
        tenant_id: str,
        admin_user,
        test_user,
        test_role,
        test_org_unit,
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

        # Create another org unit
        custom_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Custom Org 3",
            type="church",
        )
        db.add(custom_org)
        db.commit()

        # Give admin_user access to custom_org
        from app.common.models import OrgAssignment
        admin_assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=admin_user.id,
            org_unit_id=custom_org.id,
            role_id=test_role.id,
            scope_type="self",
        )
        db.add(admin_assignment)
        db.commit()

        # Create assignment with custom_set scope and custom unit
        assignment = OrgAssignmentService.create_assignment(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=test_role.id,
            scope_type="custom_set",
            custom_org_unit_ids=[custom_org.id],
        )

        # Remove custom unit
        OrgAssignmentService.remove_custom_unit(
            db=db,
            remover_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            assignment_id=assignment.id,
            org_unit_id=custom_org.id,
        )

        # Verify removed
        remaining = db.execute(
            select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assignment.id,
                OrgAssignmentUnit.org_unit_id == custom_org.id,
            )
        ).scalar_one_or_none()
        assert remaining is None


class TestAuditLogService:
    """Tests for AuditLogService."""

    def test_list_audit_logs_success(
        self, db: Session, tenant_id: str, admin_user, test_org_unit
    ):
        """Test listing audit logs."""
        from app.common.audit import create_audit_log
        from datetime import datetime, timezone

        # Create some audit logs
        log1 = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
            after_json={"name": "Test Org"},
        )
        log2 = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="update",
            entity_type="org_units",
            entity_id=test_org_unit.id,
            before_json={"name": "Test Org"},
            after_json={"name": "Updated Org"},
        )
        db.commit()

        # List logs
        logs, total = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
        )

        assert total >= 2
        assert len(logs) >= 2
        assert any(log.id == log1.id for log in logs)
        assert any(log.id == log2.id for log in logs)

    def test_list_audit_logs_with_filters(
        self, db: Session, tenant_id: str, admin_user, test_org_unit
    ):
        """Test listing audit logs with filters."""
        from app.common.audit import create_audit_log
        from datetime import datetime, timezone

        # Create audit logs
        log1 = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        log2 = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="update",
            entity_type="roles",
            entity_id=uuid4(),
        )
        db.commit()

        # Filter by entity_type
        logs, total = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            entity_type="org_units",
        )

        assert total >= 1
        assert any(log.id == log1.id for log in logs)
        assert not any(log.id == log2.id for log in logs)

    def test_list_audit_logs_with_actor_filter(
        self, db: Session, tenant_id: str, admin_user, test_user, test_org_unit
    ):
        """Test listing audit logs filtered by actor."""
        from app.common.audit import create_audit_log

        # Create logs by different actors
        log1 = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        log2 = create_audit_log(
            db=db,
            actor_id=test_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        # Filter by actor_id
        logs, total = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            actor_id=admin_user.id,
        )

        assert total >= 1
        assert any(log.id == log1.id for log in logs)
        assert not any(log.id == log2.id for log in logs)

    def test_list_audit_logs_with_date_range(
        self, db: Session, tenant_id: str, admin_user, test_org_unit
    ):
        """Test listing audit logs with date range filter."""
        from app.common.audit import create_audit_log
        from datetime import datetime, timezone, timedelta

        # Create a log
        log = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        # Filter by date range (last hour)
        start_date = datetime.now(timezone.utc) - timedelta(hours=1)
        end_date = datetime.now(timezone.utc) + timedelta(hours=1)

        logs, total = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            start_date=start_date,
            end_date=end_date,
        )

        assert total >= 1
        assert any(log.id == log.id for log in logs)

    def test_list_audit_logs_pagination(
        self, db: Session, tenant_id: str, admin_user, test_org_unit
    ):
        """Test pagination of audit logs."""
        from app.common.audit import create_audit_log

        # Create multiple logs
        for i in range(5):
            create_audit_log(
                db=db,
                actor_id=admin_user.id,
                action="create",
                entity_type="org_units",
                entity_id=test_org_unit.id,
            )
        db.commit()

        # Get first page
        logs1, total1 = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            limit=2,
            offset=0,
        )

        # Get second page
        logs2, total2 = AuditLogService.list_audit_logs(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            limit=2,
            offset=2,
        )

        assert total1 == total2
        assert len(logs1) == 2
        assert len(logs2) == 2
        assert logs1[0].id != logs2[0].id

    def test_list_audit_logs_unauthorized(
        self, db: Session, tenant_id: str, test_user
    ):
        """Test listing audit logs without permission."""
        with pytest.raises(ValueError, match="User lacks required permission"):
            AuditLogService.list_audit_logs(
                db=db,
                viewer_id=test_user.id,
                tenant_id=UUID(tenant_id),
            )

    def test_get_audit_log_success(
        self, db: Session, tenant_id: str, admin_user, test_org_unit
    ):
        """Test getting a single audit log."""
        from app.common.audit import create_audit_log

        log = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
            after_json={"name": "Test Org"},
        )
        db.commit()

        retrieved = AuditLogService.get_audit_log(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            log_id=log.id,
        )

        assert retrieved is not None
        assert retrieved.id == log.id
        assert retrieved.action == "create"
        assert retrieved.entity_type == "org_units"

    def test_get_audit_log_not_found(
        self, db: Session, tenant_id: str, admin_user
    ):
        """Test getting non-existent audit log."""
        fake_id = uuid4()
        log = AuditLogService.get_audit_log(
            db=db,
            viewer_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            log_id=fake_id,
        )

        assert log is None

    def test_get_audit_log_unauthorized(
        self, db: Session, tenant_id: str, test_user, admin_user, test_org_unit
    ):
        """Test getting audit log without permission."""
        from app.common.audit import create_audit_log

        log = create_audit_log(
            db=db,
            actor_id=admin_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        with pytest.raises(ValueError, match="User lacks required permission"):
            AuditLogService.get_audit_log(
                db=db,
                viewer_id=test_user.id,
                tenant_id=UUID(tenant_id),
                log_id=log.id,
            )

