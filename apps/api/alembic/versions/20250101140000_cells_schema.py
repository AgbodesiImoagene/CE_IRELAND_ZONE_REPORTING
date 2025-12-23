"""cells schema

Revision ID: 20250101140000
Revises: 20250101130001
Create Date: 2025-01-01 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101140000"
down_revision: Union[str, None] = "20250101130001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Cells domain tables."""
    # Create enums only if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE meeting_day AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE meeting_type AS ENUM ('prayer_planning', 'bible_study', 'outreach');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cell_report_status AS ENUM ('submitted', 'reviewed', 'approved');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create cells table
    op.create_table(
        "cells",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("leader_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assistant_leader_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("venue", sa.String(length=200), nullable=True),
        sa.Column(
            "meeting_day",
            postgresql.ENUM("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", name="meeting_day", create_type=False),
            nullable=True,
        ),
        sa.Column("meeting_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cells")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_cells_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leader_id"],
            ["people.id"],
            name=op.f("fk_cells_leader_id_people"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assistant_leader_id"],
            ["people.id"],
            name=op.f("fk_cells_assistant_leader_id_people"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("tenant_id", "org_unit_id", "name", name=op.f("uq_cells_tenant_org_name")),
    )
    op.create_index(op.f("ix_cells_tenant_id"), "cells", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_cells_tenant_org"), "cells", ["tenant_id", "org_unit_id"], unique=False)
    op.create_index(op.f("ix_cells_leader_id"), "cells", ["leader_id"], unique=False)

    # Create cell_reports table
    op.create_table(
        "cell_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cell_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_time", sa.Time(), nullable=True),
        sa.Column("attendance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_timers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_converts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("testimonies", sa.Text(), nullable=True),
        sa.Column("offerings_total", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column(
            "meeting_type",
            postgresql.ENUM("prayer_planning", "bible_study", "outreach", name="meeting_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("submitted", "reviewed", "approved", name="cell_report_status", create_type=False),
            nullable=False,
            server_default="'submitted'",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cell_reports")),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["cells.id"],
            name=op.f("fk_cell_reports_cell_id_cells"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "cell_id", "report_date", name=op.f("uq_cell_reports_tenant_cell_date")),
    )
    op.create_index(op.f("ix_cell_reports_tenant_id"), "cell_reports", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_cell_reports_tenant_cell"), "cell_reports", ["tenant_id", "cell_id"], unique=False)
    op.create_index(op.f("ix_cell_reports_date"), "cell_reports", ["report_date"], unique=False)

    # Add foreign key constraint from finance_entries.cell_id to cells.id
    op.create_foreign_key(
        op.f("fk_finance_entries_cell_id_cells"),
        "finance_entries",
        "cells",
        ["cell_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add foreign key constraint from memberships.cell_id to cells.id
    op.create_foreign_key(
        op.f("fk_memberships_cell_id_cells"),
        "memberships",
        "cells",
        ["cell_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop Cells domain tables."""
    # Drop foreign key constraints first
    op.drop_constraint(op.f("fk_finance_entries_cell_id_cells"), "finance_entries", type_="foreignkey")
    op.drop_constraint(op.f("fk_memberships_cell_id_cells"), "memberships", type_="foreignkey")

    # Drop tables
    op.drop_table("cell_reports")
    op.drop_table("cells")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS cell_report_status")
    op.execute("DROP TYPE IF EXISTS meeting_type")
    op.execute("DROP TYPE IF EXISTS meeting_day")

