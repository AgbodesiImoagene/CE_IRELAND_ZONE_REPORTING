"""registry schema

Revision ID: 20250101120000
Revises: 202511011515
Create Date: 2025-01-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101120000"
down_revision: Union[str, None] = "202511011515"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Registry domain tables."""
    # Create enums only if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE gender AS ENUM ('male', 'female', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE marital_status AS ENUM ('single', 'married', 'divorced', 'widowed', 'separated');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE membership_status AS ENUM ('visitor', 'regular', 'member', 'partner');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE first_timer_status AS ENUM ('New', 'Contacted', 'Returned', 'Member');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE service_type AS ENUM ('Sunday', 'Midweek', 'Special');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE department_role AS ENUM ('leader', 'member');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create people table
    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_code", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=20), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column(
            "gender",
            postgresql.ENUM("male", "female", "other", name="gender", create_type=False),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("town", sa.String(length=100), nullable=True),
        sa.Column("county", sa.String(length=100), nullable=True),
        sa.Column("eircode", sa.String(length=10), nullable=True),
        sa.Column(
            "marital_status",
            postgresql.ENUM("single", "married", "divorced", "widowed", "separated", name="marital_status", create_type=False),
            nullable=True,
        ),
        sa.Column("consent_contact", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("consent_data_storage", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_people_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_people")),
        sa.UniqueConstraint("tenant_id", "member_code", name=op.f("uq_people_tenant_member_code")),
    )
    op.create_index(op.f("ix_people_tenant_id"), "people", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_people_tenant_org"), "people", ["tenant_id", "org_unit_id"], unique=False
    )
    op.create_index(op.f("ix_people_org_unit_id"), "people", ["org_unit_id"], unique=False)

    # Create memberships table
    op.create_table(
        "memberships",
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("visitor", "regular", "member", "partner", name="membership_status", create_type=False),
            nullable=False,
            server_default="visitor",
        ),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("foundation_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("baptism_date", sa.Date(), nullable=True),
        sa.Column("cell_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_memberships_person_id_people"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("person_id", name=op.f("pk_memberships")),
    )
    # Note: cell_id FK will be added when cells table exists
    op.create_index(op.f("ix_memberships_cell_id"), "memberships", ["cell_id"], unique=False)

    # Create services table
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("service_time", sa.Time(), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_services_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint(
            "tenant_id",
            "org_unit_id",
            "service_date",
            "name",
            name=op.f("uq_services_tenant_org_date_name"),
        ),
    )
    op.create_index(op.f("ix_services_tenant_id"), "services", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_services_tenant_org"), "services", ["tenant_id", "org_unit_id"], unique=False
    )
    op.create_index(op.f("ix_services_org_unit_id"), "services", ["org_unit_id"], unique=False)

    # Create attendance table
    op.create_table(
        "attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("men_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("women_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("teens_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kids_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_timers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_converts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_attendance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_attendance_service_id_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance")),
        sa.UniqueConstraint("tenant_id", "service_id", name=op.f("uq_attendance_tenant_service")),
    )
    op.create_index(op.f("ix_attendance_tenant_id"), "attendance", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_attendance_service_id"), "attendance", ["service_id"], unique=True)

    # Create first_timers table
    op.create_table(
        "first_timers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("New", "Contacted", "Returned", "Member", name="first_timer_status", create_type=False),
            nullable=False,
            server_default=text("'New'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_first_timers_person_id_people"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_first_timers_service_id_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_first_timers")),
    )
    op.create_index(op.f("ix_first_timers_tenant_id"), "first_timers", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_first_timers_service_id"), "first_timers", ["service_id"], unique=False)

    # Create departments table
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_departments_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
    )
    op.create_index(
        op.f("ix_departments_tenant_id"), "departments", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_departments_tenant_org"), "departments", ["tenant_id", "org_unit_id"], unique=False
    )
    op.create_index(
        op.f("ix_departments_org_unit_id"), "departments", ["org_unit_id"], unique=False
    )

    # Create department_roles table
    op.create_table(
        "department_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("leader", "member", name="department_role", create_type=False),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["dept_id"],
            ["departments.id"],
            name=op.f("fk_department_roles_dept_id_departments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_department_roles_person_id_people"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_department_roles")),
    )
    op.create_index(
        op.f("ix_department_roles_dept_person"), "department_roles", ["dept_id", "person_id"], unique=False
    )
    op.create_index(op.f("ix_department_roles_dept_id"), "department_roles", ["dept_id"], unique=False)
    op.create_index(
        op.f("ix_department_roles_person_id"), "department_roles", ["person_id"], unique=False
    )


def downgrade() -> None:
    """Drop Registry domain tables."""
    op.drop_table("department_roles")
    op.drop_table("departments")
    op.drop_table("first_timers")
    op.drop_table("attendance")
    op.drop_table("services")
    op.drop_table("memberships")
    op.drop_table("people")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS department_role")
    op.execute("DROP TYPE IF EXISTS service_type")
    op.execute("DROP TYPE IF EXISTS first_timer_status")
    op.execute("DROP TYPE IF EXISTS membership_status")
    op.execute("DROP TYPE IF EXISTS marital_status")
    op.execute("DROP TYPE IF EXISTS gender")

