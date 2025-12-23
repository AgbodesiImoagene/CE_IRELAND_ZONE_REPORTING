"""Cells domain models (cells, cell reports)."""

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
    Integer,
    Numeric,
    TIMESTAMP,
    Uuid,
    Date,
    Time,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import (
    Base,
    MeetingDay,
    MeetingType,
    CellReportStatus,
)


class Cell(Base):
    """Cell groups (small fellowship units) within churches."""

    __tablename__ = "cells"

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
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    leader_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_leader_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    venue: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    meeting_day: Mapped[Optional[str]] = mapped_column(MeetingDay, nullable=True)
    meeting_time: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active, inactive
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
        UniqueConstraint("tenant_id", "org_unit_id", "name", name="uq_cells_tenant_org_name"),
        Index("ix_cells_tenant_org", "tenant_id", "org_unit_id"),
    )


class CellReport(Base):
    """Cell meeting reports with attendance, testimonies, and offerings."""

    __tablename__ = "cell_reports"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    cell_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cells.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    report_time: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    attendance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_timers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_converts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    testimonies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offerings_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    meeting_type: Mapped[str] = mapped_column(MeetingType, nullable=False)
    status: Mapped[str] = mapped_column(
        CellReportStatus, nullable=False, default="submitted"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        UniqueConstraint(
            "tenant_id", "cell_id", "report_date", name="uq_cell_reports_tenant_cell_date"
        ),
        Index("ix_cell_reports_tenant_cell", "tenant_id", "cell_id"),
        Index("ix_cell_reports_date", "report_date"),
    )

