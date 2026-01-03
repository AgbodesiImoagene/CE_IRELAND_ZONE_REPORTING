"""add export progress fields

Revision ID: 20250101180000
Revises: 20250101170000
Create Date: 2025-01-01 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250101180000"
down_revision: Union[str, None] = "20250101170000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add progress tracking fields to export_jobs table."""
    op.add_column(
        "export_jobs",
        sa.Column("total_rows", sa.Integer(), nullable=True),
    )
    op.add_column(
        "export_jobs",
        sa.Column("processed_rows", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    """Remove progress tracking fields from export_jobs table."""
    op.drop_column("export_jobs", "processed_rows")
    op.drop_column("export_jobs", "total_rows")

