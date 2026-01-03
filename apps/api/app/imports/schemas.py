"""Pydantic schemas for Import module."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportUploadRequest(BaseModel):
    """Request to upload a file for import."""

    entity_type: str = Field(..., description="Entity type: people, memberships, first_timers, services, attendance, cells, cell_reports, finance_entries")
    import_mode: str = Field(
        default="create_only",
        pattern="^(create_only|update_existing)$",
        description="Import mode: create_only or update_existing",
    )


class ColumnMappingConfig(BaseModel):
    """Column mapping configuration."""

    source_column: str
    target_field: str
    coercion_type: Optional[str] = None
    required: bool = False
    default_value: Optional[Any] = None


class ImportMappingRequest(BaseModel):
    """Request to update column mapping."""

    mapping_config: dict[str, ColumnMappingConfig] = Field(
        ..., description="Dictionary mapping source columns to target fields"
    )


class ImportExecuteRequest(BaseModel):
    """Request to execute import."""

    dry_run: bool = Field(
        default=False, description="If true, validate only without importing"
    )


class ImportJobResponse(BaseModel):
    """Response with import job details."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    entity_type: str
    file_name: str
    file_format: str
    file_size: int
    status: str
    import_mode: str
    total_rows: int
    processed_rows: int
    imported_count: int
    error_count: int
    skipped_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportPreviewResponse(BaseModel):
    """Response with import preview data."""

    job_id: UUID
    total_rows: int
    sample_rows: list[dict[str, Any]] = Field(
        ..., description="First 10 rows with coerced values"
    )
    mapping_suggestions: dict[str, dict[str, Any]] = Field(
        ..., description="Auto-detected column mappings"
    )
    validation_summary: dict[str, int] = Field(
        ..., description="Error counts by type"
    )
    warnings: list[str] = Field(default_factory=list)


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    row_number: int
    field: str
    error_type: str
    message: str
    original_value: Optional[Any]
    suggestion: Optional[str] = None


class ImportValidationResponse(BaseModel):
    """Response with validation results."""

    job_id: UUID
    total_errors: int
    errors_by_type: dict[str, int]
    sample_errors: list[ValidationErrorResponse] = Field(
        ..., description="Sample errors (first 100)"
    )


class ColumnMappingSuggestion(BaseModel):
    """Column mapping suggestion."""

    source_column: str
    suggested_target: Optional[str] = None
    confidence_score: int = Field(..., ge=0, le=100)
    required: bool = False
    all_candidates: list[dict[str, Any]] = Field(default_factory=list)

