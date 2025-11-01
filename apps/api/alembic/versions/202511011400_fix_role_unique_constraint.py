"""fix_role_unique_constraint

Revision ID: 202511011400
Revises: 202511011300
Create Date: 2025-11-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '202511011400'
down_revision: Union[str, None] = '202511011300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix role name uniqueness constraint.

    Change from unique(name) to unique(tenant_id, name) to allow
    the same role name in different tenants.
    """
    # Drop the old unique constraint on name only
    op.drop_constraint('uq_roles_name', 'roles', type_='unique')
    
    # Add composite unique constraint on (tenant_id, name)
    op.create_unique_constraint(
        'uq_roles_tenant_name',
        'roles',
        ['tenant_id', 'name']
    )


def downgrade() -> None:
    """Revert to unique constraint on name only."""
    # Drop composite constraint
    op.drop_constraint('uq_roles_tenant_name', 'roles', type_='unique')
    
    # Restore simple unique constraint on name
    op.create_unique_constraint(
        'uq_roles_name',
        'roles',
        ['name']
    )

