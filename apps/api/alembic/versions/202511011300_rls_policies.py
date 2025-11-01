"""rls_policies

Revision ID: 202511011300
Revises: 202511011258
Create Date: 2025-11-01 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '202511011300'
down_revision: Union[str, None] = '202511011258'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable RLS and create policies on tenant tables.
    
    Note: RLS can be toggled via ENABLE_RLS env var.
    This migration creates policies but does not enforce them unless RLS is enabled.
    """
    
    # Note: We'll enable RLS per-table, but the policies will only be enforced
    # when PostgreSQL RLS is enabled on the table.
    # The config flag (enable_rls) controls whether we SET session variables.
    
    # Enable RLS on users table
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY users_select_policy ON users
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)
    
    # Enable RLS on roles table
    op.execute("ALTER TABLE roles ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY roles_select_policy ON roles
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)
    
    # Enable RLS on org_units table
    op.execute("ALTER TABLE org_units ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY org_units_select_policy ON org_units
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND (
                -- Allow if user has access to this org or its ancestors
                has_org_access(id) = true
                OR EXISTS (
                    -- Allow if user has access to any descendant
                    SELECT 1
                    FROM org_units ou
                    WHERE is_descendant_org(ou.id, id) = true
                      AND has_org_access(ou.id) = true
                )
            )
        )
    """)
    
    # Enable RLS on org_assignments table
    op.execute("ALTER TABLE org_assignments ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY org_assignments_select_policy ON org_assignments
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND (
                -- Users can see their own assignments
                user_id = current_setting('app.user_id', true)::uuid
                OR has_org_access(org_unit_id) = true
            )
        )
    """)
    
    # Enable RLS on user_invitations table
    op.execute("ALTER TABLE user_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY user_invitations_select_policy ON user_invitations
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('system.users.create') = true
        )
    """)
    
    # Enable RLS on audit_logs table
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY audit_logs_select_policy ON audit_logs
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND (
                -- Users can see logs where they are the actor
                actor_id = current_setting('app.user_id', true)::uuid
                OR has_perm('audit.logs.read') = true
            )
        )
    """)


def downgrade() -> None:
    """Drop RLS policies and disable RLS on tables."""
    
    # Drop policies
    op.execute("DROP POLICY IF EXISTS audit_logs_select_policy ON audit_logs")
    op.execute("DROP POLICY IF EXISTS user_invitations_select_policy ON user_invitations")
    op.execute("DROP POLICY IF EXISTS org_assignments_select_policy ON org_assignments")
    op.execute("DROP POLICY IF EXISTS org_units_select_policy ON org_units")
    op.execute("DROP POLICY IF EXISTS roles_select_policy ON roles")
    op.execute("DROP POLICY IF EXISTS users_select_policy ON users")
    
    # Disable RLS
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_invitations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE org_assignments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE org_units DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE roles DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

