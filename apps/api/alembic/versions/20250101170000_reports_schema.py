"""reports schema

Revision ID: 20250101170000
Revises: 20250101160000
Create Date: 2025-01-01 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101170000"
down_revision: Union[str, None] = "20250101160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Reports domain tables."""
    # Create report_templates table first (export_jobs references it)
    op.create_table(
        "report_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("query_definition", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("visualization_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("pdf_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("shared_with_org_units", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_templates")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_templates_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_report_templates_tenant_user", "report_templates", ["tenant_id", "user_id"])
    op.create_index("ix_report_templates_shared", "report_templates", ["is_shared"])
    op.create_index("ix_report_templates_created_at", "report_templates", ["created_at"])

    # Create export_jobs table
    op.create_table(
        "report_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("query_definition", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("visualization_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("pdf_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("shared_with_org_units", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_templates")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_templates_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_report_templates_tenant_user", "report_templates", ["tenant_id", "user_id"])
    op.create_index("ix_report_templates_shared", "report_templates", ["is_shared"])
    op.create_index("ix_report_templates_created_at", "report_templates", ["created_at"])

    # Create report_schedules table
    op.create_table(
        "report_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("recipients", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("query_overrides", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_schedules")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_schedules_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["report_templates.id"],
            name=op.f("fk_report_schedules_template_id_report_templates"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_report_schedules_tenant_user", "report_schedules", ["tenant_id", "user_id"])
    op.create_index("ix_report_schedules_template", "report_schedules", ["template_id"])
    op.create_index("ix_report_schedules_active", "report_schedules", ["is_active"])
    op.create_index("ix_report_schedules_next_run", "report_schedules", ["next_run_at"])


def downgrade() -> None:
    """Drop Reports domain tables."""
    # Drop in reverse order (schedules first, then export_jobs, then templates)
    op.drop_index("ix_report_schedules_next_run", table_name="report_schedules")
    op.drop_index("ix_report_schedules_active", table_name="report_schedules")
    op.drop_index("ix_report_schedules_template", table_name="report_schedules")
    op.drop_index("ix_report_schedules_tenant_user", table_name="report_schedules")
    op.drop_table("report_schedules")

    op.drop_index("ix_export_jobs_template", table_name="export_jobs")
    op.drop_index("ix_export_jobs_created_at", table_name="export_jobs")
    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_tenant_user", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index("ix_report_templates_created_at", table_name="report_templates")
    op.drop_index("ix_report_templates_shared", table_name="report_templates")
    op.drop_index("ix_report_templates_tenant_user", table_name="report_templates")
    op.drop_table("report_templates")

