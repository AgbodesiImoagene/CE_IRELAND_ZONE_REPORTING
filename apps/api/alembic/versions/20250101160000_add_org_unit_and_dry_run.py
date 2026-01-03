"""add org_unit_id and dry_run to import_jobs

Revision ID: 20250101160000
Revises: 20250101150000
Create Date: 2025-01-01 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101160000"
down_revision: Union[str, None] = "20250101150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add default_org_unit_id and dry_run columns to import_jobs."""
    op.add_column(
        "import_jobs",
        sa.Column("default_org_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove default_org_unit_id and dry_run columns from import_jobs."""
    op.drop_column("import_jobs", "dry_run")
    op.drop_column("import_jobs", "default_org_unit_id")


