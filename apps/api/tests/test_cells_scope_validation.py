"""Tests for cells scope validation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.cells.scope_validation import (
    require_permission,
    validate_org_access_for_operation,
    validate_cell_leader_access,
)
from app.common.models import Cell, OrgUnit, Permission, RolePermission, OrgAssignment


@pytest.fixture
def cells_permissions(db, tenant_id, test_role):
    """Create cells permissions."""
    perms = [
        Permission(id=uuid4(), code="cells.reports.create", description="Create reports"),
        Permission(id=uuid4(), code="cells.manage", description="Manage cells"),
    ]

    for perm in perms:
        db.add(perm)
    db.flush()

    for perm in perms:
        role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
        db.add(role_perm)

    db.commit()
    return perms


@pytest.fixture
def test_cell(db, tenant_id, test_org_unit):
    """Create a test cell."""
    cell = Cell(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )
    db.add(cell)
    db.commit()
    return cell


class TestRequirePermission:
    """Test require_permission function."""

    def test_require_permission_success(self, db, tenant_id, test_user, cells_permissions, test_org_unit, test_role):
        """Test requiring permission when user has it."""
        # Get user's role from existing assignment
        from sqlalchemy import select
        from app.common.models import OrgAssignment
        
        assignment = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == test_user.id,
                OrgAssignment.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        
        # Ensure assignment exists with the role that has permissions
        if assignment:
            # Update role if needed
            assignment.role_id = test_role.id
        else:
            # Create assignment if it doesn't exist
            assignment = OrgAssignment(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                user_id=test_user.id,
                org_unit_id=test_org_unit.id,
                role_id=test_role.id,
                scope_type="self",
            )
            db.add(assignment)
        db.commit()

        # Should not raise
        require_permission(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            permission="cells.reports.create",
        )

    def test_require_permission_failure(self, db, tenant_id, test_user):
        """Test requiring permission when user lacks it."""
        with pytest.raises(ValueError, match="User lacks required permission"):
            require_permission(
                db=db,
                user_id=test_user.id,
                tenant_id=UUID(tenant_id),
                permission="cells.reports.create",
            )


class TestValidateOrgAccessForOperation:
    """Test validate_org_access_for_operation function."""

    def test_validate_org_access_no_permission(self, db, tenant_id, test_user, test_org_unit):
        """Test validating org access without permission."""
        with pytest.raises(ValueError, match="User lacks required permission"):
            validate_org_access_for_operation(
                db=db,
                user_id=test_user.id,
                tenant_id=UUID(tenant_id),
                target_org_unit_id=test_org_unit.id,
                permission="cells.reports.create",
            )


class TestValidateCellLeaderAccess:
    """Test validate_cell_leader_access function."""

    def test_validate_cell_leader_access_cell_not_found(self, db, tenant_id, test_user, cells_permissions):
        """Test validating access for non-existent cell."""
        fake_cell_id = uuid4()
        with pytest.raises(ValueError, match="Cell .* not found"):
            validate_cell_leader_access(
                db=db,
                user_id=test_user.id,
                tenant_id=UUID(tenant_id),
                cell_id=fake_cell_id,
                permission="cells.reports.create",
            )

    def test_validate_cell_leader_access_no_permission(self, db, tenant_id, test_user, test_cell):
        """Test validating cell leader access without permission."""
        with pytest.raises(ValueError, match="User lacks required permission"):
            validate_cell_leader_access(
                db=db,
                user_id=test_user.id,
                tenant_id=UUID(tenant_id),
                cell_id=test_cell.id,
                permission="cells.reports.create",
            )

