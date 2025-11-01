from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.common.models import Permission, Role, RolePermission
from app.scripts.seed_permissions import (
    ensure_permissions,
    ensure_role_permissions,
    ensure_roles,
    find_csv_path,
    load_matrix,
)


class TestLoadMatrix:
    """Test CSV loading and parsing logic."""

    def test_load_matrix_basic(self, tmp_path):
        """Test loading a basic CSV matrix."""
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "Admin,users.create,TRUE\n"
            "Admin,users.delete,false\n"
            "User,users.read,true\n"
        )

        result = load_matrix(csv_file)

        assert result == {
            "Admin": {"users.create": True, "users.delete": False},
            "User": {"users.read": True},
        }

    def test_load_matrix_various_boolean_formats(self, tmp_path):
        """Test various boolean formats are recognized."""
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "Role1,perm1,TRUE\n"
            "Role1,perm2,true\n"
            "Role1,perm3,1\n"
            "Role1,perm4,YES\n"
            "Role1,perm5,FALSE\n"
            "Role1,perm6,false\n"
            "Role1,perm7,0\n"
            "Role1,perm8,NO\n"
        )

        result = load_matrix(csv_file)

        assert result["Role1"]["perm1"] is True
        assert result["Role1"]["perm2"] is True
        assert result["Role1"]["perm3"] is True
        assert result["Role1"]["perm4"] is True
        assert result["Role1"]["perm5"] is False
        assert result["Role1"]["perm6"] is False
        assert result["Role1"]["perm7"] is False
        assert result["Role1"]["perm8"] is False

    def test_load_matrix_strips_whitespace(self, tmp_path):
        """Test that whitespace is stripped from role and permission names."""
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "  Admin  ,  users.create  ,  TRUE  \n"
            "User,users.read,true\n"
        )

        result = load_matrix(csv_file)

        assert "Admin" in result
        assert "users.create" in result["Admin"]
        assert result["Admin"]["users.create"] is True

    def test_load_matrix_multiple_roles(self, tmp_path):
        """Test loading multiple roles correctly."""
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "Admin,perm1,TRUE\n"
            "Admin,perm2,TRUE\n"
            "User,perm1,TRUE\n"
            "User,perm2,FALSE\n"
            "Guest,perm1,FALSE\n"
        )

        result = load_matrix(csv_file)

        assert len(result) == 3
        assert "Admin" in result
        assert "User" in result
        assert "Guest" in result
        assert len(result["Admin"]) == 2
        assert len(result["User"]) == 2
        assert len(result["Guest"]) == 1


class TestEnsurePermissions:
    """Test permission creation logic."""

    def test_ensure_permissions_creates_missing(self, db):
        """Test that missing permissions are created."""
        perms_to_ensure = {"perm1", "perm2", "perm3"}

        ensure_permissions(db, perms_to_ensure)
        db.commit()

        # Check all were created
        existing = db.execute(select(Permission)).scalars().all()
        codes = {p.code for p in existing}
        assert codes == perms_to_ensure

    def test_ensure_permissions_skips_existing(self, db):
        """Test that existing permissions are not duplicated."""
        # Create one permission manually
        existing_perm = Permission(id=UUID("11111111-1111-1111-1111-111111111111"), code="perm1")
        db.add(existing_perm)
        db.commit()

        # Try to ensure all permissions
        perms_to_ensure = {"perm1", "perm2", "perm3"}

        ensure_permissions(db, perms_to_ensure)
        db.commit()

        # Check we have 3 total (1 existing + 2 new)
        existing = db.execute(select(Permission)).scalars().all()
        codes = {p.code for p in existing}
        assert codes == perms_to_ensure
        assert len(existing) == 3

    def test_ensure_permissions_idempotent(self, db):
        """Test that running ensure_permissions twice is safe."""
        perms_to_ensure = {"perm1", "perm2"}

        ensure_permissions(db, perms_to_ensure)
        db.commit()

        # Run again
        ensure_permissions(db, perms_to_ensure)
        db.commit()

        # Should still have exactly 2 permissions
        existing = db.execute(select(Permission)).scalars().all()
        assert len(existing) == 2
        codes = {p.code for p in existing}
        assert codes == perms_to_ensure


class TestEnsureRoles:
    """Test role creation logic."""

    def test_ensure_roles_creates_missing(self, db, tenant_id):
        """Test that missing roles are created."""
        role_names = {"Admin", "User", "Guest"}

        role_name_to_id = ensure_roles(db, tenant_id, role_names)
        db.commit()

        # Check all were created
        assert len(role_name_to_id) == 3
        assert "Admin" in role_name_to_id
        assert "User" in role_name_to_id
        assert "Guest" in role_name_to_id

        # Verify in database
        roles = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant_id))
        ).scalars().all()
        assert len(roles) == 3
        role_names_db = {r.name for r in roles}
        assert role_names_db == role_names

    def test_ensure_roles_skips_existing(self, db, tenant_id):
        """Test that existing roles are not duplicated."""
        # Create one role manually
        existing_role = Role(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            tenant_id=UUID(tenant_id),
            name="Admin",
        )
        db.add(existing_role)
        db.commit()

        # Try to ensure all roles
        role_names = {"Admin", "User", "Guest"}

        role_name_to_id = ensure_roles(db, tenant_id, role_names)
        db.commit()

        # Should have 3 roles (1 existing + 2 new)
        roles = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant_id))
        ).scalars().all()
        assert len(roles) == 3
        # Existing role ID should be preserved
        assert role_name_to_id["Admin"] == str(existing_role.id)

    def test_ensure_roles_idempotent(self, db, tenant_id):
        """Test that running ensure_roles twice is safe."""
        role_names = {"Admin", "User"}

        role_name_to_id_1 = ensure_roles(db, tenant_id, role_names)
        db.commit()

        # Run again
        role_name_to_id_2 = ensure_roles(db, tenant_id, role_names)
        db.commit()

        # Should have same IDs
        assert role_name_to_id_1 == role_name_to_id_2
        assert len(role_name_to_id_1) == 2

    def test_ensure_roles_tenant_isolation(self, db):
        """Test that roles are isolated per tenant."""
        tenant1 = str(UUID("11111111-1111-1111-1111-111111111111"))
        tenant2 = str(UUID("22222222-2222-2222-2222-222222222222"))

        # Create same role name for different tenants
        ensure_roles(db, tenant1, {"Admin"})
        db.commit()
        ensure_roles(db, tenant2, {"Admin"})
        db.commit()

        # Both should exist
        roles1 = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant1))
        ).scalars().all()
        roles2 = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant2))
        ).scalars().all()

        assert len(roles1) == 1
        assert len(roles2) == 1
        assert roles1[0].name == "Admin"
        assert roles2[0].name == "Admin"
        assert roles1[0].id != roles2[0].id  # Different IDs


class TestEnsureRolePermissions:
    """Test role-permission linking logic."""

    def test_ensure_role_permissions_links_granted_only(self, db, tenant_id):
        """Test that only granted permissions are linked."""
        # Create permissions
        perm1 = Permission(id=UUID("11111111-1111-1111-1111-111111111111"), code="perm1")
        perm2 = Permission(id=UUID("22222222-2222-2222-2222-222222222222"), code="perm2")
        perm3 = Permission(id=UUID("33333333-3333-3333-3333-333333333333"), code="perm3")
        db.add_all([perm1, perm2, perm3])
        db.commit()

        # Create role
        role = Role(id=UUID("44444444-4444-4444-4444-444444444444"), tenant_id=UUID(tenant_id), name="Admin")
        db.add(role)
        db.commit()

        # Matrix: perm1=True, perm2=False, perm3=True
        role_to_perms = {
            "Admin": {
                "perm1": True,
                "perm2": False,
                "perm3": True,
            }
        }
        role_name_to_id = {"Admin": str(role.id)}

        ensure_role_permissions(db, role_name_to_id, role_to_perms)
        db.commit()

        # Check only perm1 and perm3 are linked
        links = db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).scalars().all()

        assert len(links) == 2
        perm_ids = {str(link.permission_id) for link in links}
        assert str(perm1.id) in perm_ids
        assert str(perm3.id) in perm_ids
        assert str(perm2.id) not in perm_ids

    def test_ensure_role_permissions_skips_existing(self, db, tenant_id):
        """Test that existing links are not duplicated."""
        # Create permission and role
        perm = Permission(id=UUID("11111111-1111-1111-1111-111111111111"), code="perm1")
        role = Role(id=UUID("22222222-2222-2222-2222-222222222222"), tenant_id=UUID(tenant_id), name="Admin")
        db.add_all([perm, role])
        db.commit()

        # Create existing link
        existing_link = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(existing_link)
        db.commit()

        # Run ensure
        role_to_perms = {"Admin": {"perm1": True}}
        role_name_to_id = {"Admin": str(role.id)}

        ensure_role_permissions(db, role_name_to_id, role_to_perms)
        db.commit()

        # Should still have exactly 1 link
        links = db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).scalars().all()
        assert len(links) == 1

    def test_ensure_role_permissions_idempotent(self, db, tenant_id):
        """Test that running ensure_role_permissions twice is safe."""
        # Setup
        perm = Permission(id=UUID("11111111-1111-1111-1111-111111111111"), code="perm1")
        role = Role(id=UUID("22222222-2222-2222-2222-222222222222"), tenant_id=UUID(tenant_id), name="Admin")
        db.add_all([perm, role])
        db.commit()

        role_to_perms = {"Admin": {"perm1": True}}
        role_name_to_id = {"Admin": str(role.id)}

        # Run twice
        ensure_role_permissions(db, role_name_to_id, role_to_perms)
        db.commit()
        ensure_role_permissions(db, role_name_to_id, role_to_perms)
        db.commit()

        # Should have exactly 1 link
        links = db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).scalars().all()
        assert len(links) == 1

    def test_ensure_role_permissions_multiple_roles(self, db, tenant_id):
        """Test linking permissions for multiple roles."""
        # Create permissions
        perm1 = Permission(id=UUID("11111111-1111-1111-1111-111111111111"), code="perm1")
        perm2 = Permission(id=UUID("22222222-2222-2222-2222-222222222222"), code="perm2")
        db.add_all([perm1, perm2])
        db.commit()

        # Create roles
        admin_role = Role(id=UUID("33333333-3333-3333-3333-333333333333"), tenant_id=UUID(tenant_id), name="Admin")
        user_role = Role(id=UUID("44444444-4444-4444-4444-444444444444"), tenant_id=UUID(tenant_id), name="User")
        db.add_all([admin_role, user_role])
        db.commit()

        # Matrix
        role_to_perms = {
            "Admin": {"perm1": True, "perm2": True},
            "User": {"perm1": True, "perm2": False},
        }
        role_name_to_id = {
            "Admin": str(admin_role.id),
            "User": str(user_role.id),
        }

        ensure_role_permissions(db, role_name_to_id, role_to_perms)
        db.commit()

        # Check Admin has both permissions
        admin_links = db.execute(
            select(RolePermission).where(RolePermission.role_id == admin_role.id)
        ).scalars().all()
        assert len(admin_links) == 2

        # Check User has only perm1
        user_links = db.execute(
            select(RolePermission).where(RolePermission.role_id == user_role.id)
        ).scalars().all()
        assert len(user_links) == 1
        assert user_links[0].permission_id == perm1.id


class TestFindCsvPath:
    """Test CSV path resolution logic."""

    def test_find_csv_path_env_override(self, tmp_path, monkeypatch):
        """Test that PERMISSIONS_CSV_PATH env var is used if set."""
        csv_file = tmp_path / "custom.csv"
        csv_file.write_text("role_name,permission,default_granted\n")
        monkeypatch.setenv("PERMISSIONS_CSV_PATH", str(csv_file))

        result = find_csv_path()

        assert result == csv_file

    def test_find_csv_path_env_override_missing_file(self, tmp_path, monkeypatch):
        """Test that missing env override file does not raise error."""
        missing_file = tmp_path / "missing.csv"
        monkeypatch.setenv("PERMISSIONS_CSV_PATH", str(missing_file))

        result = find_csv_path()
        assert result.match("resources/permissions_matrix.csv")

    def test_find_csv_path_fallback_error(self, monkeypatch, tmp_path):
        """Test that FileNotFoundError is raised when no CSV is found."""
        # Remove env var
        monkeypatch.delenv("PERMISSIONS_CSV_PATH", raising=False)
        # Patch CSV_CANDIDATE_PATHS to point to non-existent files
        from app.scripts import seed_permissions
        original_paths = seed_permissions.CSV_CANDIDATE_PATHS
        non_existent = tmp_path / "nonexistent" / "permissions_matrix.csv"
        seed_permissions.CSV_CANDIDATE_PATHS = [non_existent]

        try:
            with pytest.raises(FileNotFoundError, match="not found"):
                find_csv_path()
        finally:
            seed_permissions.CSV_CANDIDATE_PATHS = original_paths

    def test_find_csv_path_uses_test_file(self, tmp_path, monkeypatch):
        """Test with a test CSV file in expected location."""
        csv_file = tmp_path / "permissions_matrix.csv"
        csv_file.write_text("role_name,permission,default_granted\n")
        monkeypatch.delenv("PERMISSIONS_CSV_PATH", raising=False)
        # Mock the candidate paths to point to our temp file
        # This is a bit tricky without patching, so we'll use env override
        monkeypatch.setenv("PERMISSIONS_CSV_PATH", str(csv_file))

        result = find_csv_path()

        assert result == csv_file


class TestFullIntegration:
    """Test full seeding workflow integration."""

    def test_full_seed_workflow(self, db, tenant_id, tmp_path):
        """Test complete seeding workflow from CSV."""
        # Create test CSV
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "Admin,users.create,TRUE\n"
            "Admin,users.delete,TRUE\n"
            "Admin,users.read,FALSE\n"
            "User,users.read,TRUE\n"
            "User,users.create,FALSE\n"
        )

        # Load and process
        matrix = load_matrix(csv_file)
        all_perms = {perm for perms in matrix.values() for perm in perms.keys()}
        role_names = set(matrix.keys())

        # Ensure permissions
        ensure_permissions(db, all_perms)
        db.commit()

        # Ensure roles
        role_name_to_id = ensure_roles(db, tenant_id, role_names)
        db.commit()

        # Ensure role permissions
        ensure_role_permissions(db, role_name_to_id, matrix)
        db.commit()

        # Verify results
        permissions = db.execute(select(Permission)).scalars().all()
        assert len(permissions) == 3  # users.create, users.delete, users.read
        perm_codes = {p.code for p in permissions}
        assert perm_codes == {"users.create", "users.delete", "users.read"}

        roles = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant_id))
        ).scalars().all()
        assert len(roles) == 2  # Admin, User
        role_names_db = {r.name for r in roles}
        assert role_names_db == {"Admin", "User"}

        # Check Admin has 2 permissions
        admin_role = next(r for r in roles if r.name == "Admin")
        admin_links = db.execute(
            select(RolePermission).where(RolePermission.role_id == admin_role.id)
        ).scalars().all()
        assert len(admin_links) == 2

        # Check User has 1 permission
        user_role = next(r for r in roles if r.name == "User")
        user_links = db.execute(
            select(RolePermission).where(RolePermission.role_id == user_role.id)
        ).scalars().all()
        assert len(user_links) == 1

    def test_full_seed_idempotent(self, db, tenant_id, tmp_path):
        """Test that full seed workflow is idempotent."""
        # Create test CSV
        csv_file = tmp_path / "test_matrix.csv"
        csv_file.write_text(
            "role_name,permission,default_granted\n"
            "Admin,users.create,TRUE\n"
            "User,users.read,TRUE\n"
        )

        # Run workflow twice
        for _ in range(2):
            matrix = load_matrix(csv_file)
            all_perms = {perm for perms in matrix.values() for perm in perms.keys()}
            role_names = set(matrix.keys())

            ensure_permissions(db, all_perms)
            db.commit()

            role_name_to_id = ensure_roles(db, tenant_id, role_names)
            db.commit()

            ensure_role_permissions(db, role_name_to_id, matrix)
            db.commit()

        # Verify no duplicates
        permissions = db.execute(select(Permission)).scalars().all()
        assert len(permissions) == 2

        roles = db.execute(
            select(Role).where(Role.tenant_id == UUID(tenant_id))
        ).scalars().all()
        assert len(roles) == 2

        # Count total links
        all_links = db.execute(select(RolePermission)).scalars().all()
        assert len(all_links) == 2  # One per role

