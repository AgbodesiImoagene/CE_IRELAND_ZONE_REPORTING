"""imports schema

Revision ID: 20250101150000
Revises: 20250101140000
Create Date: 2025-01-01 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101150000"
down_revision: Union[str, None] = "20250101140000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Import domain tables."""
    # Create import_jobs table
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("mapping_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("import_mode", sa.String(length=20), nullable=False, server_default="create_only"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_errors", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_file_path", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_import_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_import_jobs_tenant_id"), "import_jobs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_tenant_user"), "import_jobs", ["tenant_id", "user_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_status"), "import_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_import_jobs_created_at"), "import_jobs", ["created_at"], unique=False)

    # Create import_errors table
    op.create_table(
        "import_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.String(length=200), nullable=True),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_errors")),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_errors_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_import_errors_import_job_id"), "import_errors", ["import_job_id"], unique=False)
    op.create_index(op.f("ix_import_errors_job_row"), "import_errors", ["import_job_id", "row_number"], unique=False)


def downgrade() -> None:
    """Drop Import domain tables."""
    op.drop_index(op.f("ix_import_errors_job_row"), table_name="import_errors")
    op.drop_index(op.f("ix_import_errors_import_job_id"), table_name="import_errors")
    op.drop_table("import_errors")
    op.drop_index(op.f("ix_import_jobs_created_at"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_status"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_tenant_user"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_tenant_id"), table_name="import_jobs")
    op.drop_table("import_jobs")

