"""add sent_at to user_secrets

Revision ID: 202512231200
Revises: 202511011400
Create Date: 2025-12-23 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202512231200"
down_revision: Union[str, None] = "202511011400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sent_at timestamp column to user_secrets table."""
    op.add_column(
        "user_secrets",
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove sent_at column from user_secrets table."""
    op.drop_column("user_secrets", "sent_at")

