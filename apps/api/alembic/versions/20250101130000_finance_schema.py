"""finance schema

Revision ID: 20250101130000
Revises: 20250101120001
Create Date: 2025-01-01 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250101130000"
down_revision: Union[str, None] = "20250101120001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Finance domain tables."""
    # Create enums only if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payment_method AS ENUM ('cash', 'kingspay', 'bank_transfer', 'pos', 'cheque', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE verified_status AS ENUM ('draft', 'verified', 'reconciled', 'locked');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE batch_status AS ENUM ('draft', 'locked');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE partnership_cadence AS ENUM ('weekly', 'monthly', 'quarterly', 'annual');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE partnership_status AS ENUM ('active', 'paused', 'ended');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_type AS ENUM ('manual', 'cell_report');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create funds table
    op.create_table(
        "funds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_partnership", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_funds")),
        sa.UniqueConstraint("tenant_id", "name", name=op.f("uq_funds_tenant_name")),
    )
    op.create_index(op.f("ix_funds_tenant_id"), "funds", ["tenant_id"], unique=False)

    # Create partnership_arms table
    op.create_table(
        "partnership_arms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partnership_arms")),
        sa.UniqueConstraint("tenant_id", "name", name=op.f("uq_partnership_arms_tenant_name")),
    )
    op.create_index(op.f("ix_partnership_arms_tenant_id"), "partnership_arms", ["tenant_id"], unique=False)

    # Create batches table
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "locked", name="batch_status", create_type=False),
            nullable=False,
            server_default=text("'draft'"),
        ),
        sa.Column("locked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verified_by_1", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_by_2", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_batches_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_batches_service_id_services"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.UniqueConstraint(
            "tenant_id",
            "org_unit_id",
            "service_id",
            name=op.f("uq_batches_tenant_org_service"),
        ),
    )
    op.create_index(op.f("ix_batches_tenant_id"), "batches", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_batches_tenant_org"), "batches", ["tenant_id", "org_unit_id"], unique=False
    )
    op.create_index(op.f("ix_batches_org_unit_id"), "batches", ["org_unit_id"], unique=False)
    op.create_index(op.f("ix_batches_service_id"), "batches", ["service_id"], unique=False)

    # Create finance_entries table
    op.create_table(
        "finance_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fund_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partnership_arm_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="'EUR'"),
        sa.Column(
            "method",
            postgresql.ENUM("cash", "kingspay", "bank_transfer", "pos", "cheque", "other", name="payment_method", create_type=False),
            nullable=False,
        ),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cell_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_giver_name", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "verified_status",
            postgresql.ENUM("draft", "verified", "reconciled", "locked", name="verified_status", create_type=False),
            nullable=False,
            server_default=text("'draft'"),
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM("manual", "cell_report", name="source_type", create_type=False),
            nullable=False,
            server_default=text("'manual'"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_units.id"],
            name=op.f("fk_finance_entries_org_unit_id_org_units"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["batches.id"],
            name=op.f("fk_finance_entries_batch_id_batches"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_finance_entries_service_id_services"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fund_id"],
            ["funds.id"],
            name=op.f("fk_finance_entries_fund_id_funds"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partnership_arm_id"],
            ["partnership_arms.id"],
            name=op.f("fk_finance_entries_partnership_arm_id_partnership_arms"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_finance_entries_person_id_people"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_entries")),
    )
    op.create_index(op.f("ix_finance_entries_tenant_id"), "finance_entries", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_finance_entries_tenant_org_date"),
        "finance_entries",
        ["tenant_id", "org_unit_id", "transaction_date"],
        unique=False,
    )
    op.create_index(op.f("ix_finance_entries_org_unit_id"), "finance_entries", ["org_unit_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_batch_id"), "finance_entries", ["batch_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_service_id"), "finance_entries", ["service_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_fund_id"), "finance_entries", ["fund_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_partnership_arm_id"), "finance_entries", ["partnership_arm_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_person_id"), "finance_entries", ["person_id"], unique=False)
    op.create_index(op.f("ix_finance_entries_cell_id"), "finance_entries", ["cell_id"], unique=False)

    # Create partnerships table
    op.create_table(
        "partnerships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fund_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partnership_arm_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "cadence",
            postgresql.ENUM("weekly", "monthly", "quarterly", "annual", name="partnership_cadence", create_type=False),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("active", "paused", "ended", name="partnership_status", create_type=False),
            nullable=False,
            server_default=text("'active'"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_partnerships_person_id_people"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fund_id"],
            ["funds.id"],
            name=op.f("fk_partnerships_fund_id_funds"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partnership_arm_id"],
            ["partnership_arms.id"],
            name=op.f("fk_partnerships_partnership_arm_id_partnership_arms"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partnerships")),
    )
    op.create_index(op.f("ix_partnerships_tenant_id"), "partnerships", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_partnerships_tenant_person"), "partnerships", ["tenant_id", "person_id"], unique=False
    )
    op.create_index(op.f("ix_partnerships_person_id"), "partnerships", ["person_id"], unique=False)
    op.create_index(op.f("ix_partnerships_fund_id"), "partnerships", ["fund_id"], unique=False)
    op.create_index(op.f("ix_partnerships_partnership_arm_id"), "partnerships", ["partnership_arm_id"], unique=False)


def downgrade() -> None:
    """Drop Finance domain tables."""
    op.drop_table("partnerships")
    op.drop_table("finance_entries")
    op.drop_table("batches")
    op.drop_table("partnership_arms")
    op.drop_table("funds")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS source_type")
    op.execute("DROP TYPE IF EXISTS partnership_status")
    op.execute("DROP TYPE IF EXISTS partnership_cadence")
    op.execute("DROP TYPE IF EXISTS batch_status")
    op.execute("DROP TYPE IF EXISTS verified_status")
    op.execute("DROP TYPE IF EXISTS payment_method")

