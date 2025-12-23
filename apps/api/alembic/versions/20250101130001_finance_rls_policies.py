"""finance rls_policies

Revision ID: 20250101130001
Revises: 20250101130000
Create Date: 2025-01-01 13:00:01.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20250101130001"
down_revision: Union[str, None] = "20250101130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable RLS and create policies on Finance tables.

    Policies check:
    - tenant_id matches current tenant
    - User has required permission (finance.*.*)
    - User has org access via has_org_access() where applicable
    """

    # Funds table
    op.execute("ALTER TABLE funds ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY funds_select_policy ON funds
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY funds_insert_policy ON funds
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY funds_update_policy ON funds
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY funds_delete_policy ON funds
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )

    # Partnership arms table
    op.execute("ALTER TABLE partnership_arms ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY partnership_arms_select_policy ON partnership_arms
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnership_arms_insert_policy ON partnership_arms
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnership_arms_update_policy ON partnership_arms
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnership_arms_delete_policy ON partnership_arms
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.lookups.manage') = true
        )
    """
    )

    # Batches table
    op.execute("ALTER TABLE batches ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY batches_select_policy ON batches
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.batches.read') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY batches_insert_policy ON batches
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.batches.create') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY batches_update_policy ON batches
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.batches.update') = true
            AND has_org_access(org_unit_id) = true
            AND status = 'draft'
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.batches.update') = true
            AND has_org_access(org_unit_id) = true
            AND status = 'draft'
        )
    """
    )
    op.execute(
        """
        CREATE POLICY batches_delete_policy ON batches
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.batches.delete') = true
            AND has_org_access(org_unit_id) = true
            AND status = 'draft'
        )
    """
    )

    # Finance entries table
    op.execute("ALTER TABLE finance_entries ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY finance_entries_select_policy ON finance_entries
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.read') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY finance_entries_insert_policy ON finance_entries
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.create') = true
            AND has_org_access(org_unit_id) = true
        )
    """
    )
    op.execute(
        """
        CREATE POLICY finance_entries_update_policy ON finance_entries
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.update') = true
            AND has_org_access(org_unit_id) = true
            AND verified_status != 'locked'
            AND NOT EXISTS (
                SELECT 1 FROM batches b
                WHERE b.id = finance_entries.batch_id
                  AND b.status = 'locked'
            )
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.update') = true
            AND has_org_access(org_unit_id) = true
            AND verified_status != 'locked'
            AND NOT EXISTS (
                SELECT 1 FROM batches b
                WHERE b.id = finance_entries.batch_id
                  AND b.status = 'locked'
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY finance_entries_delete_policy ON finance_entries
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.delete') = true
            AND has_org_access(org_unit_id) = true
            AND verified_status != 'locked'
            AND NOT EXISTS (
                SELECT 1 FROM batches b
                WHERE b.id = finance_entries.batch_id
                  AND b.status = 'locked'
            )
        )
    """
    )

    # Partnerships table
    op.execute("ALTER TABLE partnerships ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY partnerships_select_policy ON partnerships
        FOR SELECT
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.partnerships.read') = true
            AND EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = partnerships.person_id
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnerships_insert_policy ON partnerships
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.create') = true
            AND EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = partnerships.person_id
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnerships_update_policy ON partnerships
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.update') = true
            AND EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = partnerships.person_id
                  AND has_org_access(p.org_unit_id) = true
            )
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.update') = true
            AND EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = partnerships.person_id
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )
    op.execute(
        """
        CREATE POLICY partnerships_delete_policy ON partnerships
        FOR DELETE
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND has_perm('finance.entries.delete') = true
            AND EXISTS (
                SELECT 1 FROM people p
                WHERE p.id = partnerships.person_id
                  AND has_org_access(p.org_unit_id) = true
            )
        )
    """
    )


def downgrade() -> None:
    """Drop RLS policies and disable RLS on Finance tables."""

    # Drop policies
    op.execute("DROP POLICY IF EXISTS partnerships_delete_policy ON partnerships")
    op.execute("DROP POLICY IF EXISTS partnerships_update_policy ON partnerships")
    op.execute("DROP POLICY IF EXISTS partnerships_insert_policy ON partnerships")
    op.execute("DROP POLICY IF EXISTS partnerships_select_policy ON partnerships")

    op.execute("DROP POLICY IF EXISTS finance_entries_delete_policy ON finance_entries")
    op.execute("DROP POLICY IF EXISTS finance_entries_update_policy ON finance_entries")
    op.execute("DROP POLICY IF EXISTS finance_entries_insert_policy ON finance_entries")
    op.execute("DROP POLICY IF EXISTS finance_entries_select_policy ON finance_entries")

    op.execute("DROP POLICY IF EXISTS batches_delete_policy ON batches")
    op.execute("DROP POLICY IF EXISTS batches_update_policy ON batches")
    op.execute("DROP POLICY IF EXISTS batches_insert_policy ON batches")
    op.execute("DROP POLICY IF EXISTS batches_select_policy ON batches")

    op.execute("DROP POLICY IF EXISTS partnership_arms_delete_policy ON partnership_arms")
    op.execute("DROP POLICY IF EXISTS partnership_arms_update_policy ON partnership_arms")
    op.execute("DROP POLICY IF EXISTS partnership_arms_insert_policy ON partnership_arms")
    op.execute("DROP POLICY IF EXISTS partnership_arms_select_policy ON partnership_arms")

    op.execute("DROP POLICY IF EXISTS funds_delete_policy ON funds")
    op.execute("DROP POLICY IF EXISTS funds_update_policy ON funds")
    op.execute("DROP POLICY IF EXISTS funds_insert_policy ON funds")
    op.execute("DROP POLICY IF EXISTS funds_select_policy ON funds")

    # Disable RLS
    op.execute("ALTER TABLE partnerships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE finance_entries DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE batches DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE partnership_arms DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE funds DISABLE ROW LEVEL SECURITY")

