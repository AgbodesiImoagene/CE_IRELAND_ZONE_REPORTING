"""Import domain models (import jobs, import errors)."""

from __future__ import annotations

from datetime import datetime, timezone
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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import Base


class ImportJob(Base):
    """Import job tracking table."""

    __tablename__ = "import_jobs"

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
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "people", "memberships", "first_timers", "services", "attendance"
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "csv", "xlsx", "json", "tsv"
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # S3/MinIO path
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # bytes
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )  # "pending", "previewing", "mapping", "validating", "queued", "processing", "completed", "failed"
    mapping_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Column mappings and coercion rules
    import_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="create_only"
    )  # "create_only", "update_existing"
    default_org_unit_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )  # Default org unit for imports
    dry_run: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )  # If True, only validate without importing
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_errors: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Array of error objects
    error_file_path: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )  # S3 path to error report CSV
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
        Index("ix_import_jobs_tenant_user", "tenant_id", "user_id"),
        Index("ix_import_jobs_status", "status"),
        Index("ix_import_jobs_created_at", "created_at"),
    )


class ImportError(Base):
    """Detailed import error tracking (optional, for detailed tracking)."""

    __tablename__ = "import_errors"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    import_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "validation", "coercion", "constraint", "duplicate", "reference"
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    original_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_import_errors_job_row", "import_job_id", "row_number"),
    )

