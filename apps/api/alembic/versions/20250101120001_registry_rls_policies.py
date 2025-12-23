"""registry rls_policies

Revision ID: 20250101120001
Revises: 20250101120000
Create Date: 2025-01-01 12:00:01.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20250101120001"
down_revision: Union[str, None] = "20250101120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable RLS and create policies on Registry tables.

    Policies check:
    - tenant_id matches current tenant
    - User has required permission (registry.*.*)
    - User has org access via has_org_access()
    """

    # People table
    op.execute("ALTER TABLE people ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY people_select_policy ON people
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.people.read') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY people_insert_policy ON people
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.people.create') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY people_update_policy ON people
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.people.update') = true
            AND has_org_access(org_unit_id) = true
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.people.update') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY people_delete_policy ON people
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.people.delete') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )

    # Memberships table
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY memberships_select_policy ON memberships
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = memberships.person_id
                  AND p.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.people.read') = true
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY memberships_insert_policy ON memberships
        FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = memberships.person_id
                  AND p.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.people.update') = true
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY memberships_update_policy ON memberships
        FOR UPDATE
        USING (
            EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = memberships.person_id
                  AND p.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.people.update') = true
                  AND has_org_access(p.org_unit_id) = true
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = memberships.person_id
                  AND p.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.people.update') = true
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )

    # Services table
    op.execute("ALTER TABLE services ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY services_select_policy ON services
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.read') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY services_insert_policy ON services
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.create') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )

    # Attendance table
    op.execute("ALTER TABLE attendance ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY attendance_select_policy ON attendance
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.read') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = attendance.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY attendance_insert_policy ON attendance
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.create') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = attendance.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY attendance_update_policy ON attendance
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.update') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = attendance.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.update') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = attendance.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY attendance_delete_policy ON attendance
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.attendance.delete') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = attendance.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )

    # First-timers table
    op.execute("ALTER TABLE first_timers ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY first_timers_select_policy ON first_timers
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.firsttimers.read') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = first_timers.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY first_timers_insert_policy ON first_timers
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.firsttimers.create') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = first_timers.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY first_timers_update_policy ON first_timers
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.firsttimers.update') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = first_timers.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.firsttimers.update') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = first_timers.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY first_timers_delete_policy ON first_timers
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.firsttimers.delete') = true
            AND EXISTS (
                SELECT 1 FROM services s
                WHERE s.id = first_timers.service_id
                  AND has_org_access(s.org_unit_id) = true
            )
        )
    """
    )

    # Departments table
    op.execute("ALTER TABLE departments ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY departments_select_policy ON departments
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.departments.read') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY departments_insert_policy ON departments
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.departments.create') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY departments_update_policy ON departments
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.departments.update') = true
            AND has_org_access(org_unit_id) = true
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.departments.update') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY departments_delete_policy ON departments
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('registry.departments.delete') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )

    # Department roles table
    op.execute("ALTER TABLE department_roles ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY department_roles_select_policy ON department_roles
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM departments d
                WHERE d.id = department_roles.dept_id
                  AND d.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.departments.read') = true
                  AND has_org_access(d.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY department_roles_insert_policy ON department_roles
        FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM departments d
                WHERE d.id = department_roles.dept_id
                  AND d.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.departments.update') = true
                  AND has_org_access(d.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY department_roles_update_policy ON department_roles
        FOR UPDATE
        USING (
            EXISTS (
                SELECT 1 FROM departments d
                WHERE d.id = department_roles.dept_id
                  AND d.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.departments.update') = true
                  AND has_org_access(d.org_unit_id) = true
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM departments d
                WHERE d.id = department_roles.dept_id
                  AND d.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.departments.update') = true
                  AND has_org_access(d.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY department_roles_delete_policy ON department_roles
        FOR DELETE
        USING (
            EXISTS (
                SELECT 1 FROM departments d
                WHERE d.id = department_roles.dept_id
                  AND d.tenant_id = current_setting('app.tenant_id', true)::uuid
                  AND has_perm('registry.departments.update') = true
                  AND has_org_access(d.org_unit_id) = true
            )
        )
    """
    )


def downgrade() -> None:
    """Drop RLS policies and disable RLS on Registry tables."""

    # Drop policies
    op.execute("DROP POLICY IF EXISTS department_roles_delete_policy ON department_roles")
    op.execute("DROP POLICY IF EXISTS department_roles_update_policy ON department_roles")
    op.execute("DROP POLICY IF EXISTS department_roles_insert_policy ON department_roles")
    op.execute("DROP POLICY IF EXISTS department_roles_select_policy ON department_roles")

    op.execute("DROP POLICY IF EXISTS departments_delete_policy ON departments")
    op.execute("DROP POLICY IF EXISTS departments_update_policy ON departments")
    op.execute("DROP POLICY IF EXISTS departments_insert_policy ON departments")
    op.execute("DROP POLICY IF EXISTS departments_select_policy ON departments")

    op.execute("DROP POLICY IF EXISTS first_timers_delete_policy ON first_timers")
    op.execute("DROP POLICY IF EXISTS first_timers_update_policy ON first_timers")
    op.execute("DROP POLICY IF EXISTS first_timers_insert_policy ON first_timers")
    op.execute("DROP POLICY IF EXISTS first_timers_select_policy ON first_timers")

    op.execute("DROP POLICY IF EXISTS attendance_delete_policy ON attendance")
    op.execute("DROP POLICY IF EXISTS attendance_update_policy ON attendance")
    op.execute("DROP POLICY IF EXISTS attendance_insert_policy ON attendance")
    op.execute("DROP POLICY IF EXISTS attendance_select_policy ON attendance")

    op.execute("DROP POLICY IF EXISTS services_insert_policy ON services")
    op.execute("DROP POLICY IF EXISTS services_select_policy ON services")

    op.execute("DROP POLICY IF EXISTS memberships_update_policy ON memberships")
    op.execute("DROP POLICY IF EXISTS memberships_insert_policy ON memberships")
    op.execute("DROP POLICY IF EXISTS memberships_select_policy ON memberships")

    op.execute("DROP POLICY IF EXISTS people_delete_policy ON people")
    op.execute("DROP POLICY IF EXISTS people_update_policy ON people")
    op.execute("DROP POLICY IF EXISTS people_insert_policy ON people")
    op.execute("DROP POLICY IF EXISTS people_select_policy ON people")

    # Disable RLS
    op.execute("ALTER TABLE department_roles DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE departments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE first_timers DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attendance DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE services DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE people DISABLE ROW LEVEL SECURITY")

