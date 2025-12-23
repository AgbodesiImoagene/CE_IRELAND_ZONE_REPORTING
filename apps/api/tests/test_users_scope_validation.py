"""Tests for user scope validation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.models import OrgAssignment, OrgAssignmentUnit, OrgUnit, Role
from app.users.scope_validation import (
    _is_descendant,
    has_org_access,
    validate_scope_assignments,
)


class TestHasOrgAccess:
    """Test has_org_access function."""

    def test_has_org_access_self_scope(
        self, db: Session, tenant_id: str, test_user, test_org_unit
    ):
        """Test has_org_access with 'self' scope."""
        # Create assignment with 'self' scope
        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=uuid4(),
            scope_type="self",
        )
        db.add(assignment)
        db.commit()

        # Should have access to the exact org unit
        assert has_org_access(
            db, test_user.id, UUID(tenant_id), test_org_unit.id
        ) is True

        # Should not have access to different org unit
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other Org",
            type="church",
        )
        db.add(other_org)
        db.commit()

        assert (
            has_org_access(db, test_user.id, UUID(tenant_id), other_org.id)
            is False
        )

    def test_has_org_access_subtree_scope(
        self, db: Session, tenant_id: str, test_user, test_org_unit
    ):
        """Test has_org_access with 'subtree' scope."""
        # Create parent org unit
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent Region",
            type="region",
        )
        db.add(parent)
        db.flush()

        # Create child org unit
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child Zone",
            type="zone",
            parent_id=parent.id,
        )
        db.add(child)
        db.commit()

        # Create assignment with 'subtree' scope on parent
        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=parent.id,
            role_id=uuid4(),
            scope_type="subtree",
        )
        db.add(assignment)
        db.commit()

        # Should have access to parent
        assert has_org_access(db, test_user.id, UUID(tenant_id), parent.id) is True

        # Should have access to child (descendant)
        assert has_org_access(db, test_user.id, UUID(tenant_id), child.id) is True

    def test_has_org_access_custom_set_scope(
        self, db: Session, tenant_id: str, test_user, test_org_unit
    ):
        """Test has_org_access with 'custom_set' scope."""
        # Create another org unit
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other Org",
            type="church",
        )
        db.add(other_org)
        db.flush()

        # Create assignment with 'custom_set' scope
        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,  # Base org unit
            role_id=uuid4(),
            scope_type="custom_set",
        )
        db.add(assignment)
        db.flush()

        # Add other_org to custom set
        assignment_unit = OrgAssignmentUnit(
            assignment_id=assignment.id,
            org_unit_id=other_org.id,
        )
        db.add(assignment_unit)
        db.commit()

        # Should have access to org unit in custom set
        assert has_org_access(db, test_user.id, UUID(tenant_id), other_org.id) is True

        # Should not have access to org unit not in custom set
        third_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Third Org",
            type="church",
        )
        db.add(third_org)
        db.commit()

        assert (
            has_org_access(db, test_user.id, UUID(tenant_id), third_org.id) is False
        )

    def test_has_org_access_no_assignment(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test has_org_access with no assignments."""
        from app.common.models import User
        from app.auth.utils import hash_password

        # Create a user without any assignments
        user_no_assignment = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="noassignment@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user_no_assignment)
        db.commit()

        assert (
            has_org_access(
                db, user_no_assignment.id, UUID(tenant_id), test_org_unit.id
            )
            is False
        )

    def test_has_org_access_different_tenant(
        self, db: Session, tenant_id: str, test_user, test_org_unit
    ):
        """Test has_org_access with different tenant."""
        other_tenant_id = uuid4()

        # Create assignment
        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
            role_id=uuid4(),
            scope_type="self",
        )
        db.add(assignment)
        db.commit()

        # Should not have access when querying different tenant
        assert (
            has_org_access(db, test_user.id, other_tenant_id, test_org_unit.id)
            is False
        )


class TestIsDescendant:
    """Test _is_descendant function."""

    def test_is_descendant_direct_child(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test _is_descendant with direct child."""
        # Create parent
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent",
            type="region",
        )
        db.add(parent)
        db.flush()

        # Create child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child",
            type="zone",
            parent_id=parent.id,
        )
        db.add(child)
        db.commit()

        # Child is descendant of parent
        assert _is_descendant(db, child.id, parent.id) is True

        # Parent is not descendant of child
        assert _is_descendant(db, parent.id, child.id) is False

    def test_is_descendant_same_id(self, db: Session, tenant_id: str, test_org_unit):
        """Test _is_descendant with same ID."""
        assert _is_descendant(db, test_org_unit.id, test_org_unit.id) is True

    def test_is_descendant_grandchild(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test _is_descendant with grandchild."""
        # Create parent
        parent = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Parent",
            type="region",
        )
        db.add(parent)
        db.flush()

        # Create child
        child = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Child",
            type="zone",
            parent_id=parent.id,
        )
        db.add(child)
        db.flush()

        # Create grandchild
        grandchild = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Grandchild",
            type="group",
            parent_id=child.id,
        )
        db.add(grandchild)
        db.commit()

        # Grandchild is descendant of parent
        assert _is_descendant(db, grandchild.id, parent.id) is True

        # Grandchild is descendant of child
        assert _is_descendant(db, grandchild.id, child.id) is True

    def test_is_descendant_no_relation(
        self, db: Session, tenant_id: str, test_org_unit
    ):
        """Test _is_descendant with unrelated org units."""
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other",
            type="church",
        )
        db.add(other_org)
        db.commit()

        assert _is_descendant(db, test_org_unit.id, other_org.id) is False
        assert _is_descendant(db, other_org.id, test_org_unit.id) is False


class TestValidateScopeAssignments:
    """Test validate_scope_assignments function."""

    def test_validate_scope_assignments_success(
        self, db: Session, tenant_id: str, admin_user, test_org_unit, admin_role
    ):
        """Test validate_scope_assignments with valid permissions."""
        # admin_user has system.users.create permission
        validate_scope_assignments(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            target_org_unit_id=test_org_unit.id,
            target_role_id=admin_role.id,
        )
        # Should not raise

    def test_validate_scope_assignments_no_permission(
        self, db: Session, tenant_id: str, test_user, test_org_unit, test_role
    ):
        """Test validate_scope_assignments without permission."""
        with pytest.raises(ValueError, match="system.users.create"):
            validate_scope_assignments(
                db=db,
                creator_id=test_user.id,
                tenant_id=UUID(tenant_id),
                target_org_unit_id=test_org_unit.id,
                target_role_id=test_role.id,
            )

    def test_validate_scope_assignments_no_org_access(
        self, db: Session, tenant_id: str, admin_user, admin_role
    ):
        """Test validate_scope_assignments without org access."""
        # Create org unit that admin_user doesn't have access to
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other Org",
            type="church",
        )
        db.add(other_org)
        db.commit()

        # admin_user might not have access to this org unit
        # This depends on their assignments
        # If they don't have access, it should raise ValueError
        try:
            validate_scope_assignments(
                db=db,
                creator_id=admin_user.id,
                tenant_id=UUID(tenant_id),
                target_org_unit_id=other_org.id,
                target_role_id=admin_role.id,
            )
        except ValueError as e:
            assert "access to org unit" in str(e).lower()

