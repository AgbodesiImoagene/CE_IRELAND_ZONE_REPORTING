"""IAM service layer for org units, roles, permissions, assignments, and audit logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, or_, text
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.common.models import (
    OrgUnit,
    Role,
    Permission,
    RolePermission,
    OrgAssignment,
    OrgAssignmentUnit,
    User,
    AuditLog,
)
from app.core.config import settings
from app.iam.scope_validation import require_iam_permission


class OrgUnitService:
    """Service for managing organizational units."""

    @staticmethod
    def list_org_units(
        db: Session,
        tenant_id: UUID,
        type_filter: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[OrgUnit], int]:
        """List org units with optional filters and pagination."""
        stmt = select(OrgUnit).where(OrgUnit.tenant_id == tenant_id)

        if type_filter:
            stmt = stmt.where(OrgUnit.type == type_filter)

        if parent_id is not None:
            stmt = stmt.where(OrgUnit.parent_id == parent_id)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(OrgUnit.name.ilike(search_pattern))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(OrgUnit.name).limit(limit).offset(offset)

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_org_unit(
        db: Session, org_unit_id: UUID, tenant_id: UUID
    ) -> Optional[OrgUnit]:
        """Get a single org unit."""
        return db.execute(
            select(OrgUnit).where(
                OrgUnit.id == org_unit_id,
                OrgUnit.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def create_org_unit(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        name: str,
        type: str,
        parent_id: Optional[UUID] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OrgUnit:
        """Create a new org unit."""
        require_iam_permission(db, creator_id, tenant_id, "system.org_units.create")

        # Validate parent if provided
        if parent_id:
            parent = OrgUnitService.get_org_unit(db, parent_id, tenant_id)
            if not parent:
                raise ValueError(f"Parent org unit {parent_id} not found")

            # Validate hierarchy (parent type must be higher in hierarchy)
            hierarchy = {"region": 0, "zone": 1, "group": 2, "church": 3, "outreach": 4}
            parent_level = hierarchy.get(parent.type, -1)
            child_level = hierarchy.get(type, -1)

            if child_level <= parent_level:
                raise ValueError(
                    f"Cannot create {type} under {parent.type}. Org unit type must be lower in hierarchy."
                )

        # Check for duplicate name at same level
        existing = db.execute(
            select(OrgUnit).where(
                OrgUnit.tenant_id == tenant_id,
                OrgUnit.name == name,
                OrgUnit.parent_id == parent_id,
            )
        ).scalar_one_or_none()

        if existing:
            raise ValueError(
                f"Org unit with name '{name}' already exists at this level"
            )

        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            type=type,
            parent_id=parent_id,
        )
        db.add(org_unit)
        db.flush()

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "org_units",
            org_unit.id,
            None,
            {
                "id": str(org_unit.id),
                "name": name,
                "type": type,
                "parent_id": str(parent_id) if parent_id else None,
            },
            ip,
            user_agent,
        )

        db.commit()
        db.refresh(org_unit)
        return org_unit

    @staticmethod
    def update_org_unit(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        name: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OrgUnit:
        """Update an org unit."""
        require_iam_permission(db, updater_id, tenant_id, "system.org_units.update")

        org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
        if not org_unit:
            raise ValueError(f"Org unit {org_unit_id} not found")

        before_json = {
            "name": org_unit.name,
            "type": org_unit.type,
            "parent_id": str(org_unit.parent_id) if org_unit.parent_id else None,
        }

        # Validate parent change
        if parent_id is not None and parent_id != org_unit.parent_id:
            if parent_id:  # Moving to a new parent
                new_parent = OrgUnitService.get_org_unit(db, parent_id, tenant_id)
                if not new_parent:
                    raise ValueError(f"Parent org unit {parent_id} not found")

                # Prevent circular reference (can't be parent of itself or its ancestors)
                if parent_id == org_unit_id:
                    raise ValueError("Org unit cannot be its own parent")

                # Check if new parent is a descendant
                descendants = OrgUnitService.get_subtree(db, org_unit_id, tenant_id)
                if any(d.id == parent_id for d in descendants):
                    raise ValueError("Cannot set parent to a descendant org unit")

                # Validate hierarchy
                hierarchy = {"region": 0, "zone": 1, "group": 2, "church": 3, "outreach": 4}
                parent_level = hierarchy.get(new_parent.type, -1)
                child_level = hierarchy.get(org_unit.type, -1)

                if child_level <= parent_level:
                    raise ValueError(
                        f"Cannot move {org_unit.type} under {new_parent.type}"
                    )

            # Check for duplicate name at new level
            duplicate = db.execute(
                select(OrgUnit).where(
                    OrgUnit.tenant_id == tenant_id,
                    OrgUnit.name == (name or org_unit.name),
                    OrgUnit.parent_id == parent_id,
                    OrgUnit.id != org_unit_id,
                )
            ).scalar_one_or_none()

            if duplicate:
                raise ValueError(
                    f"Org unit with name '{name or org_unit.name}' already exists at this level"
                )

        if name is not None:
            org_unit.name = name
        if parent_id is not None:
            org_unit.parent_id = parent_id

        after_json = {
            "name": org_unit.name,
            "type": org_unit.type,
            "parent_id": str(org_unit.parent_id) if org_unit.parent_id else None,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "org_units",
            org_unit_id,
            before_json,
            after_json,
            ip,
            user_agent,
        )

        db.commit()
        db.refresh(org_unit)
        return org_unit

    @staticmethod
    def delete_org_unit(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Delete an org unit."""
        require_iam_permission(db, deleter_id, tenant_id, "system.org_units.delete")

        org_unit = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)
        if not org_unit:
            raise ValueError(f"Org unit {org_unit_id} not found")

        # Check for children
        children = OrgUnitService.get_children(db, org_unit_id, tenant_id)
        if children:
            raise ValueError("Cannot delete org unit with children. Delete children first.")

        # Check for assignments (users assigned to this org unit)
        assignments = db.execute(
            select(OrgAssignment).where(OrgAssignment.org_unit_id == org_unit_id)
        ).scalars().all()

        if assignments:
            raise ValueError(
                "Cannot delete org unit with user assignments. Reassign users first."
            )

        # Check for people records
        from app.common.models import People

        people_count = db.execute(
            select(func.count()).where(People.org_unit_id == org_unit_id)
        ).scalar() or 0

        if people_count > 0:
            raise ValueError(
                "Cannot delete org unit with associated people records. Reassign people first."
            )

        before_json = {
            "id": str(org_unit.id),
            "name": org_unit.name,
            "type": org_unit.type,
            "parent_id": str(org_unit.parent_id) if org_unit.parent_id else None,
        }

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "org_units",
            org_unit_id,
            before_json,
            None,
            ip,
            user_agent,
        )

        db.delete(org_unit)
        db.commit()

    @staticmethod
    def get_children(
        db: Session, org_unit_id: UUID, tenant_id: UUID
    ) -> list[OrgUnit]:
        """Get direct children of an org unit."""
        return list(
            db.execute(
                select(OrgUnit).where(
                    OrgUnit.parent_id == org_unit_id,
                    OrgUnit.tenant_id == tenant_id,
                )
            ).scalars().all()
        )

    @staticmethod
    def get_subtree(
        db: Session, org_unit_id: UUID, tenant_id: UUID
    ) -> list[OrgUnit]:
        """Get all descendants of an org unit (recursive)."""
        # Use PostgreSQL recursive CTE for efficiency
        # For SQLite, use iterative approach
        try:
            dialect_name = db.bind.dialect.name
        except (AttributeError, TypeError):
            dialect_name = "sqlite"

        if dialect_name == "postgresql":
            stmt = text("""
                WITH RECURSIVE subtree AS (
                    SELECT id, tenant_id, name, type, parent_id
                    FROM org_units
                    WHERE id = :org_unit_id
                    UNION ALL
                    SELECT ou.id, ou.tenant_id, ou.name, ou.type, ou.parent_id
                    FROM org_units ou
                    INNER JOIN subtree s ON ou.parent_id = s.id
                    WHERE ou.tenant_id = :tenant_id
                )
                SELECT id, tenant_id, name, type, parent_id
                FROM subtree
                WHERE id != :org_unit_id
                ORDER BY name
            """)
            result = db.execute(
                stmt,
                {"org_unit_id": str(org_unit_id), "tenant_id": str(tenant_id)},
            )
            # Convert to OrgUnit-like dicts, then query actual objects
            rows = result.fetchall()
            if not rows:
                return []

            ids = [UUID(row[0]) for row in rows]
            return list(
                db.execute(
                    select(OrgUnit).where(OrgUnit.id.in_(ids))
                ).scalars().all()
            )
        else:
            # SQLite: iterative approach
            result = []
            queue = [org_unit_id]

            while queue:
                current_id = queue.pop(0)
                children = OrgUnitService.get_children(db, current_id, tenant_id)
                result.extend(children)
                queue.extend([child.id for child in children])

            return result

    @staticmethod
    def get_ancestors(
        db: Session, org_unit_id: UUID, tenant_id: UUID
    ) -> list[OrgUnit]:
        """Get all ancestors of an org unit (path to root)."""
        ancestors = []
        current = OrgUnitService.get_org_unit(db, org_unit_id, tenant_id)

        if not current:
            return []

        while current.parent_id:
            parent = OrgUnitService.get_org_unit(db, current.parent_id, tenant_id)
            if not parent:
                break
            ancestors.append(parent)
            current = parent

        # Reverse to get root to leaf order
        ancestors.reverse()
        return ancestors


class RoleService:
    """Service for managing roles."""

    @staticmethod
    def list_roles(
        db: Session,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Role], int]:
        """List roles with pagination."""
        stmt = select(Role).where(Role.tenant_id == tenant_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(Role.name).limit(limit).offset(offset)

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_role(
        db: Session, role_id: UUID, tenant_id: UUID
    ) -> Optional[Role]:
        """Get a single role."""
        return db.execute(
            select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
        ).scalar_one_or_none()

    @staticmethod
    def create_role(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        name: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Role:
        """Create a new role."""
        require_iam_permission(db, creator_id, tenant_id, "system.roles.create")

        # Check for duplicate name
        existing = db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Role with name '{name}' already exists")

        role = Role(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
        )
        db.add(role)
        db.flush()

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "roles",
            role.id,
            None,
            {
                "id": str(role.id),
                "name": name,
            },
            ip,
            user_agent,
        )

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update_role(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        role_id: UUID,
        name: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Role:
        """Update a role."""
        require_iam_permission(db, updater_id, tenant_id, "system.roles.update")

        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        before_json = {"name": role.name}

        # Check for duplicate name
        existing = db.execute(
            select(Role).where(
                Role.tenant_id == tenant_id,
                Role.name == name,
                Role.id != role_id,
            )
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Role with name '{name}' already exists")

        role.name = name

        after_json = {"name": role.name}

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "roles",
            role_id,
            before_json,
            after_json,
            ip,
            user_agent,
        )

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        role_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Delete a role."""
        require_iam_permission(db, deleter_id, tenant_id, "system.roles.delete")

        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        # Check if role is assigned to any users
        assignment_count = db.execute(
            select(func.count()).where(OrgAssignment.role_id == role_id)
        ).scalar() or 0

        if assignment_count > 0:
            raise ValueError(
                f"Cannot delete role that is assigned to {assignment_count} user(s). "
                "Reassign users first."
            )

        before_json = {
            "id": str(role.id),
            "name": role.name,
        }

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "roles",
            role_id,
            before_json,
            None,
            ip,
            user_agent,
        )

        db.delete(role)
        db.commit()

    @staticmethod
    def get_role_permissions(
        db: Session, role_id: UUID, tenant_id: UUID
    ) -> list[Permission]:
        """Get all permissions for a role."""
        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        # Load permissions through role_permissions
        stmt = (
            select(Permission)
            .join(RolePermission)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def assign_permissions(
        db: Session,
        assigner_id: UUID,
        tenant_id: UUID,
        role_id: UUID,
        permission_ids: list[UUID],
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> list[Permission]:
        """Assign permissions to a role."""
        require_iam_permission(db, assigner_id, tenant_id, "system.roles.assign")

        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        # Verify all permissions exist
        permissions = list(
            db.execute(
                select(Permission).where(Permission.id.in_(permission_ids))
            ).scalars().all()
        )

        if len(permissions) != len(permission_ids):
            found_ids = {str(p.id) for p in permissions}
            missing = [str(pid) for pid in permission_ids if str(pid) not in found_ids]
            raise ValueError(f"Permissions not found: {', '.join(missing)}")

        # Get existing permissions
        existing = db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        ).scalars().all()
        existing_ids = {rp.permission_id for rp in existing}

        # Add new permissions
        new_permissions = []
        for perm_id in permission_ids:
            if perm_id not in existing_ids:
                role_perm = RolePermission(role_id=role_id, permission_id=perm_id)
                db.add(role_perm)
                new_permissions.append(perm_id)

        # Audit log for each new permission
        for perm_id in new_permissions:
            perm = next(p for p in permissions if p.id == perm_id)
            create_audit_log(
                db,
                assigner_id,
                "assign_permission",
                "role_permissions",
                None,
                None,
                {
                    "role_id": str(role_id),
                    "permission_id": str(perm_id),
                    "permission_code": perm.code,
                },
                ip,
                user_agent,
            )

        db.commit()

        # Return updated permissions list
        return RoleService.get_role_permissions(db, role_id, tenant_id)

    @staticmethod
    def remove_permission(
        db: Session,
        remover_id: UUID,
        tenant_id: UUID,
        role_id: UUID,
        permission_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Remove a permission from a role."""
        require_iam_permission(db, remover_id, tenant_id, "system.roles.assign")

        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        permission = db.get(Permission, permission_id)
        if not permission:
            raise ValueError(f"Permission {permission_id} not found")

        role_perm = db.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
        ).scalar_one_or_none()

        if not role_perm:
            raise ValueError(
                f"Permission {permission_id} is not assigned to role {role_id}"
            )

        # Audit log
        create_audit_log(
            db,
            remover_id,
            "remove_permission",
            "role_permissions",
            None,
            {
                "role_id": str(role_id),
                "permission_id": str(permission_id),
                "permission_code": permission.code,
            },
            None,
            ip,
            user_agent,
        )

        db.delete(role_perm)
        db.commit()

    @staticmethod
    def replace_permissions(
        db: Session,
        replacer_id: UUID,
        tenant_id: UUID,
        role_id: UUID,
        permission_ids: list[UUID],
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> list[Permission]:
        """Replace all permissions for a role (bulk update)."""
        require_iam_permission(db, replacer_id, tenant_id, "system.roles.assign")

        role = RoleService.get_role(db, role_id, tenant_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        # Get current permissions for audit log
        current_perms = RoleService.get_role_permissions(db, role_id, tenant_id)
        current_ids = {p.id for p in current_perms}

        # Verify all new permissions exist
        permissions = list(
            db.execute(
                select(Permission).where(Permission.id.in_(permission_ids))
            ).scalars().all()
        )

        if len(permissions) != len(permission_ids):
            found_ids = {str(p.id) for p in permissions}
            missing = [str(pid) for pid in permission_ids if str(pid) not in found_ids]
            raise ValueError(f"Permissions not found: {', '.join(missing)}")

        new_ids = set(permission_ids)

        # Remove permissions not in new list
        to_remove = current_ids - new_ids
        for perm_id in to_remove:
            RoleService.remove_permission(
                db, replacer_id, tenant_id, role_id, perm_id, ip, user_agent
            )

        # Add new permissions
        to_add = new_ids - current_ids
        for perm_id in to_add:
            role_perm = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(role_perm)

            perm = next(p for p in permissions if p.id == perm_id)
            create_audit_log(
                db,
                replacer_id,
                "assign_permission",
                "role_permissions",
                None,
                None,
                {
                    "role_id": str(role_id),
                    "permission_id": str(perm_id),
                    "permission_code": perm.code,
                },
                ip,
                user_agent,
            )

        db.commit()

        # Return updated permissions list
        return RoleService.get_role_permissions(db, role_id, tenant_id)


class PermissionService:
    """Service for managing permissions."""

    @staticmethod
    def list_permissions(
        db: Session,
        module_filter: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> tuple[list[Permission], int]:
        """List permissions with optional module filter."""
        stmt = select(Permission)

        if module_filter:
            # Filter by module prefix (e.g., "registry.", "finance.")
            stmt = stmt.where(Permission.code.startswith(f"{module_filter}."))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(Permission.code).limit(limit).offset(offset)

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_permission(
        db: Session, permission_id: UUID
    ) -> Optional[Permission]:
        """Get a single permission."""
        return db.get(Permission, permission_id)


class OrgAssignmentService:
    """Service for managing org assignments."""

    @staticmethod
    def list_user_assignments(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
    ) -> list[OrgAssignment]:
        """List all assignments for a user."""
        return list(
            db.execute(
                select(OrgAssignment).where(
                    OrgAssignment.user_id == user_id,
                    OrgAssignment.tenant_id == tenant_id,
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    def list_org_unit_assignments(
        db: Session,
        tenant_id: UUID,
        org_unit_id: UUID,
    ) -> list[OrgAssignment]:
        """List all assignments for an org unit."""
        return list(
            db.execute(
                select(OrgAssignment).where(
                    OrgAssignment.org_unit_id == org_unit_id,
                    OrgAssignment.tenant_id == tenant_id,
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    def create_assignment(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: UUID,
        role_id: UUID,
        scope_type: str,
        custom_org_unit_ids: Optional[list[UUID]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OrgAssignment:
        """Create a new org assignment."""
        require_iam_permission(
            db, creator_id, tenant_id, "system.users.assign"
        )

        # Validate scope assignments
        from app.users.scope_validation import validate_scope_assignments

        validate_scope_assignments(db, creator_id, tenant_id, org_unit_id, role_id)

        # Check for duplicate assignment
        existing = db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == user_id,
                OrgAssignment.org_unit_id == org_unit_id,
                OrgAssignment.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Assignment already exists for user {user_id} "
                f"and org unit {org_unit_id}"
            )

        # Create assignment
        assignment = OrgAssignment(
            tenant_id=tenant_id,
            user_id=user_id,
            org_unit_id=org_unit_id,
            role_id=role_id,
            scope_type=scope_type,
        )
        db.add(assignment)
        db.flush()

        # Create custom units if scope_type is custom_set
        if scope_type == "custom_set" and custom_org_unit_ids:
            for custom_org_id in custom_org_unit_ids:
                # Validate creator has access to each custom org
                validate_scope_assignments(
                    db, creator_id, tenant_id, custom_org_id, role_id
                )
                assignment_unit = OrgAssignmentUnit(
                    assignment_id=assignment.id,
                    org_unit_id=custom_org_id,
                )
                db.add(assignment_unit)

        # Create audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "org_assignments",
            assignment.id,
            None,
            {
                "user_id": str(user_id),
                "org_unit_id": str(org_unit_id),
                "role_id": str(role_id),
                "scope_type": scope_type,
            },
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def update_assignment(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        assignment_id: UUID,
        role_id: Optional[UUID] = None,
        scope_type: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OrgAssignment:
        """Update an org assignment."""
        require_iam_permission(
            db, updater_id, tenant_id, "system.users.assign"
        )

        assignment = db.get(OrgAssignment, assignment_id)
        if not assignment or assignment.tenant_id != tenant_id:
            raise ValueError(f"Assignment {assignment_id} not found")

        before_json = {
            "role_id": str(assignment.role_id),
            "scope_type": assignment.scope_type,
        }

        # Update role if provided
        if role_id is not None:
            # Validate updater can assign this role
            from app.users.scope_validation import validate_scope_assignments

            validate_scope_assignments(
                db, updater_id, tenant_id, assignment.org_unit_id, role_id
            )
            assignment.role_id = role_id

        # Update scope_type if provided
        if scope_type is not None:
            assignment.scope_type = scope_type
            # If changing from custom_set, remove custom units
            if assignment.scope_type != "custom_set":
                # Delete custom units
                db.execute(
                    text(
                        "DELETE FROM org_assignment_units "
                        "WHERE assignment_id = :assignment_id"
                    ),
                    {"assignment_id": assignment.id},
                )

        after_json = {
            "role_id": str(assignment.role_id),
            "scope_type": assignment.scope_type,
        }

        # Create audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "org_assignments",
            assignment_id,
            before_json,
            after_json,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def delete_assignment(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        assignment_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Delete an org assignment."""
        require_iam_permission(
            db, deleter_id, tenant_id, "system.users.assign"
        )

        assignment = db.get(OrgAssignment, assignment_id)
        if not assignment or assignment.tenant_id != tenant_id:
            raise ValueError(f"Assignment {assignment_id} not found")

        before_json = {
            "user_id": str(assignment.user_id),
            "org_unit_id": str(assignment.org_unit_id),
            "role_id": str(assignment.role_id),
            "scope_type": assignment.scope_type,
        }

        # Delete custom units first (CASCADE should handle this, but explicit is better)
        db.execute(
            text(
                "DELETE FROM org_assignment_units "
                "WHERE assignment_id = :assignment_id"
            ),
            {"assignment_id": str(assignment_id)},
        )

        # Delete assignment
        db.delete(assignment)

        # Create audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "org_assignments",
            assignment_id,
            before_json,
            None,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()

    @staticmethod
    def add_custom_unit(
        db: Session,
        adder_id: UUID,
        tenant_id: UUID,
        assignment_id: UUID,
        org_unit_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OrgAssignmentUnit:
        """Add an org unit to a custom_set assignment."""
        require_iam_permission(
            db, adder_id, tenant_id, "system.users.assign"
        )

        assignment = db.get(OrgAssignment, assignment_id)
        if not assignment or assignment.tenant_id != tenant_id:
            raise ValueError(f"Assignment {assignment_id} not found")

        if assignment.scope_type != "custom_set":
            raise ValueError(
                "Can only add custom units to assignments with custom_set scope"
            )

        # Validate adder has access to this org unit
        from app.users.scope_validation import validate_scope_assignments

        validate_scope_assignments(
            db, adder_id, tenant_id, org_unit_id, assignment.role_id
        )

        # Check if already exists
        existing = db.execute(
            select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assignment_id,
                OrgAssignmentUnit.org_unit_id == org_unit_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Org unit {org_unit_id} already in assignment {assignment_id}"
            )

        # Create custom unit
        assignment_unit = OrgAssignmentUnit(
            assignment_id=assignment_id,
            org_unit_id=org_unit_id,
        )
        db.add(assignment_unit)

        # Create audit log
        create_audit_log(
            db,
            adder_id,
            "add_custom_unit",
            "org_assignments",
            assignment_id,
            None,
            {"org_unit_id": str(org_unit_id)},
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()
        db.refresh(assignment_unit)
        return assignment_unit

    @staticmethod
    def remove_custom_unit(
        db: Session,
        remover_id: UUID,
        tenant_id: UUID,
        assignment_id: UUID,
        org_unit_id: UUID,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Remove an org unit from a custom_set assignment."""
        require_iam_permission(
            db, remover_id, tenant_id, "system.users.assign"
        )

        assignment = db.get(OrgAssignment, assignment_id)
        if not assignment or assignment.tenant_id != tenant_id:
            raise ValueError(f"Assignment {assignment_id} not found")

        if assignment.scope_type != "custom_set":
            raise ValueError(
                "Can only remove custom units from assignments with custom_set scope"
            )

        # Find and delete custom unit
        assignment_unit = db.execute(
            select(OrgAssignmentUnit).where(
                OrgAssignmentUnit.assignment_id == assignment_id,
                OrgAssignmentUnit.org_unit_id == org_unit_id,
            )
        ).scalar_one_or_none()

        if not assignment_unit:
            raise ValueError(
                f"Org unit {org_unit_id} not found in assignment {assignment_id}"
            )

        before_json = {"org_unit_id": str(org_unit_id)}

        db.delete(assignment_unit)

        # Create audit log
        create_audit_log(
            db,
            remover_id,
            "remove_custom_unit",
            "org_assignments",
            assignment_id,
            before_json,
            None,
            ip=ip,
            user_agent=user_agent,
        )

        db.commit()

    @staticmethod
    def create_bulk_assignments(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        assignments: list[dict],
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[list[OrgAssignment], list[dict]]:
        """
        Create multiple org assignments in bulk.

        Args:
            db: Database session
            creator_id: ID of the user creating assignments
            tenant_id: Tenant ID
            assignments: List of assignment dicts with keys:
                - user_id: UUID
                - org_unit_id: UUID
                - role_id: UUID
                - scope_type: str
                - custom_org_unit_ids: Optional[list[UUID]]
            ip: IP address
            user_agent: User agent string

        Returns:
            Tuple of (created assignments, failed assignments with errors)
        """
        require_iam_permission(
            db, creator_id, tenant_id, "system.users.assign"
        )

        created = []
        failed = []

        for assignment_data in assignments:
            try:
                assignment = OrgAssignmentService.create_assignment(
                    db=db,
                    creator_id=creator_id,
                    tenant_id=tenant_id,
                    user_id=assignment_data["user_id"],
                    org_unit_id=assignment_data["org_unit_id"],
                    role_id=assignment_data["role_id"],
                    scope_type=assignment_data.get("scope_type", "self"),
                    custom_org_unit_ids=assignment_data.get("custom_org_unit_ids"),
                    ip=ip,
                    user_agent=user_agent,
                )
                created.append(assignment)
            except Exception as e:
                failed.append({
                    "assignment": assignment_data,
                    "error": str(e),
                })

        return created, failed


class AuditLogService:
    """Service for accessing audit logs."""

    @staticmethod
    def list_audit_logs(
        db: Session,
        viewer_id: UUID,
        tenant_id: UUID,
        actor_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """
        List audit logs with optional filters and pagination.

        Args:
            db: Database session
            viewer_id: ID of the user viewing the logs
            tenant_id: Tenant ID
            actor_id: Filter by actor ID
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            start_date: Filter logs from this date onwards
            end_date: Filter logs up to this date
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            Tuple of (list of audit logs, total count)
        """
        require_iam_permission(db, viewer_id, tenant_id, "system.audit.view")

        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

        # Apply filters
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)

        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)

        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)

        if start_date:
            stmt = stmt.where(AuditLog.occurred_at >= start_date)

        if end_date:
            stmt = stmt.where(AuditLog.occurred_at <= end_date)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Apply pagination and ordering (most recent first)
        stmt = (
            stmt.order_by(AuditLog.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )

        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_audit_log(
        db: Session,
        viewer_id: UUID,
        tenant_id: UUID,
        log_id: UUID,
    ) -> Optional[AuditLog]:
        """
        Get a single audit log by ID.

        Args:
            db: Database session
            viewer_id: ID of the user viewing the log
            tenant_id: Tenant ID
            log_id: ID of the audit log

        Returns:
            AuditLog instance or None if not found
        """
        require_iam_permission(db, viewer_id, tenant_id, "system.audit.view")

        return db.execute(
            select(AuditLog).where(
                AuditLog.id == log_id,
                AuditLog.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

