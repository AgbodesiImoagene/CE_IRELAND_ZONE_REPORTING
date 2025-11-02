"""add retry_count to outbox_notifications

Revision ID: 202511011515
Revises: 202511011400
Create Date: 2025-11-01 15:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "202511011515"
down_revision = "202511011400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add retry_count column to outbox_notifications
    op.add_column(
        "outbox_notifications",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # Remove retry_count column
    op.drop_column("outbox_notifications", "retry_count")
