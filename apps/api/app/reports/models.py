"""Report domain models (export jobs, templates, schedules)."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timezone
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    String,
    ForeignKey,
    Index,
    Integer,
    JSON,
    TIMESTAMP,
    Uuid,
    Text,
    BigInteger,
    Boolean,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import Base


class ExportJob(Base):
    """Export job tracking table."""

    __tablename__ = "export_jobs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )  # "pending", "processing", "completed", "failed"
    format: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "csv", "xlsx", "pdf"
    query_definition: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # Complete query definition (ReportQueryRequest)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # Optional reference to template used
    file_path: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )  # S3/MinIO path when completed
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )  # File size in bytes
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Total rows to process (estimated or actual)
    processed_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )  # Rows processed so far
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
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
        Index("ix_export_jobs_tenant_user", "tenant_id", "user_id"),
        Index("ix_export_jobs_status", "status"),
        Index("ix_export_jobs_created_at", "created_at"),
        Index("ix_export_jobs_template", "template_id"),
    )


class ReportTemplate(Base):
    """Saved report query definitions."""

    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_definition: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # Complete query definition (ReportQueryRequest)
    visualization_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Chart definition (VisualizationConfig)
    pdf_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # PDF layout and styling (PDFConfig)
    is_shared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shared_with_org_units: Mapped[Optional[list[UUID]]] = mapped_column(
        JSON, nullable=True
    )  # List of org_unit_ids that can access this template
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_report_templates_tenant_user", "tenant_id", "user_id"),
        Index("ix_report_templates_shared", "is_shared"),
        Index("ix_report_templates_created_at", "created_at"),
    )


class ReportSchedule(Base):
    """Scheduled report generation."""

    __tablename__ = "report_schedules"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "daily", "weekly", "monthly", "quarterly"
    day_of_week: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 0-6 for weekly (0=Monday, 6=Sunday)
    day_of_month: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 1-31 for monthly
    time: Mapped[dt_time] = mapped_column(Time, nullable=False)  # Time of day
    recipients: Mapped[list[str]] = mapped_column(
        JSON, nullable=False
    )  # List of email addresses
    query_overrides: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Optional query parameter overrides
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
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
        Index("ix_report_schedules_tenant_user", "tenant_id", "user_id"),
        Index("ix_report_schedules_template", "template_id"),
        Index("ix_report_schedules_active", "is_active"),
        Index("ix_report_schedules_next_run", "next_run_at"),
    )
