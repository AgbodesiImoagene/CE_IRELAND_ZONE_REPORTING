"""Finance domain models (funds, partnership arms, batches, finance entries, partnerships)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    Numeric,
    TIMESTAMP,
    Uuid,
    Date,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import (
    Base,
    PaymentMethod,
    VerifiedStatus,
    BatchStatus,
    PartnershipCadence,
    PartnershipStatus,
    SourceType,
)


class Fund(Base):
    """Fund categories (tithe, offering, seed, first fruit, partnership, etc.)."""

    __tablename__ = "funds"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_partnership: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_funds_tenant_name"),
    )


class PartnershipArm(Base):
    """Partnership arms (Rhapsody, Healing School, InnerCity Mission, Loveworld TV, etc.)."""

    __tablename__ = "partnership_arms"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_from: Mapped[datetime] = mapped_column(Date, nullable=False)
    active_to: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_partnership_arms_tenant_name"),
    )


class Batch(Base):
    """Collection of finance entries per service."""

    __tablename__ = "batches"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(BatchStatus, nullable=False, default="draft")
    locked_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    verified_by_1: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    verified_by_2: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "org_unit_id",
            "service_id",
            name="uq_batches_tenant_org_service",
        ),
        Index("ix_batches_tenant_org", "tenant_id", "org_unit_id"),
    )


class FinanceEntry(Base):
    """Individual finance entry (contribution record)."""

    __tablename__ = "finance_entries"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fund_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    partnership_arm_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partnership_arms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )  # 12 digits, 2 decimal places
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    method: Mapped[str] = mapped_column(PaymentMethod, nullable=False)
    person_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cell_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cells.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_giver_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_status: Mapped[str] = mapped_column(
        VerifiedStatus, nullable=False, default="draft"
    )
    source_type: Mapped[str] = mapped_column(SourceType, nullable=False, default="manual")
    source_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_finance_entries_tenant_org_date", "tenant_id", "org_unit_id", "transaction_date"),
    )


class Partnership(Base):
    """Partnership pledge tracking and fulfilment."""

    __tablename__ = "partnerships"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fund_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    partnership_arm_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partnership_arms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cadence: Mapped[str] = mapped_column(PartnershipCadence, nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    target_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(
        PartnershipStatus, nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_partnerships_tenant_person", "tenant_id", "person_id"),
    )

