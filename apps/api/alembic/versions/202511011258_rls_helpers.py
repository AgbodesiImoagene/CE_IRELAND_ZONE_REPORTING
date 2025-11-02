"""rls_helpers

Revision ID: 202511011258
Revises: b429a8fd778c
Create Date: 2025-11-01 12:58:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202511011258"
down_revision: Union[str, None] = "b429a8fd778c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create RLS helper functions.

    These functions are used by RLS policies to check permissions and org access.
    """

    # Function to check if a permission exists in the session's permission array
    op.execute(
        """
        CREATE OR REPLACE FUNCTION has_perm(p text) RETURNS boolean AS $$
        BEGIN
            RETURN p = ANY (
                COALESCE(
                    current_setting('app.perms', true)::text[],
                    ARRAY[]::text[]
                )
            );
        EXCEPTION
            WHEN OTHERS THEN
                RETURN false;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """
    )

    # Function to check if an org unit is a descendant of another
    op.execute(
        """
        CREATE OR REPLACE FUNCTION is_descendant_org(
            target_org_id uuid,
            ancestor_org_id uuid
        ) RETURNS boolean AS $$
        DECLARE
            current_id uuid;
        BEGIN
            -- If target equals ancestor, it's not a descendant
            IF target_org_id = ancestor_org_id THEN
                RETURN false;
            END IF;
            
            -- Walk up the parent chain
            current_id := target_org_id;
            WHILE current_id IS NOT NULL LOOP
                SELECT parent_id INTO current_id
                FROM org_units
                WHERE id = current_id;
                
                -- Found ancestor in chain
                IF current_id = ancestor_org_id THEN
                    RETURN true;
                END IF;
            END LOOP;
            
            RETURN false;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """
    )

    # Function to check if current user has access to an org unit
    op.execute(
        """
        CREATE OR REPLACE FUNCTION has_org_access(target_org_id uuid) 
        RETURNS boolean AS $$
        DECLARE
            user_uuid uuid;
            assignment_record RECORD;
        BEGIN
            -- Get current user ID from session
            BEGIN
                user_uuid := current_setting('app.user_id', true)::uuid;
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN false;
            END;
            
            -- If no user, deny access
            IF user_uuid IS NULL THEN
                RETURN false;
            END IF;
            
            -- Check each assignment for the user
            FOR assignment_record IN
                SELECT 
                    oa.org_unit_id,
                    oa.scope_type,
                    oa.id as assignment_id
                FROM org_assignments oa
                WHERE oa.user_id = user_uuid
            LOOP
                -- Check 'self' scope
                IF assignment_record.scope_type = 'self' 
                   AND assignment_record.org_unit_id = target_org_id THEN
                    RETURN true;
                END IF;
                
                -- Check 'subtree' scope
                IF assignment_record.scope_type = 'subtree' 
                   AND is_descendant_org(target_org_id, assignment_record.org_unit_id) THEN
                    RETURN true;
                END IF;
                
                -- Check 'custom_set' scope
                IF assignment_record.scope_type = 'custom_set' THEN
                    IF EXISTS (
                        SELECT 1
                        FROM org_assignment_units oau
                        WHERE oau.assignment_id = assignment_record.assignment_id
                          AND oau.org_unit_id = target_org_id
                    ) THEN
                        RETURN true;
                    END IF;
                END IF;
            END LOOP;
            
            RETURN false;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """
    )


def downgrade() -> None:
    """Drop RLS helper functions."""
    op.execute("DROP FUNCTION IF EXISTS has_org_access(uuid)")
    op.execute("DROP FUNCTION IF EXISTS is_descendant_org(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS has_perm(text)")
