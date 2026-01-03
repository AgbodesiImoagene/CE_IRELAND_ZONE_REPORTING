"""Pydantic schemas for Reports module."""

from __future__ import annotations

from datetime import date, time
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Filter and Query Configuration Schemas

class FilterConfig(BaseModel):
    """Flexible filter configuration."""

    field: str
    operator: Optional[str] = None  # "eq", "in", "gte", "lte", "gt", "lt", "is_null"
    value: Any


class AggregationConfig(BaseModel):
    """Aggregation specification."""

    field: str
    function: str = Field(..., description="sum, count, avg, min, max, date_trunc")
    alias: Optional[str] = None
    params: Optional[dict[str, Any]] = Field(default_factory=dict)


class OrderByConfig(BaseModel):
    """Sorting specification."""

    field: str
    direction: str = Field(default="asc", pattern="^(asc|desc)$")


class PeriodComparison(BaseModel):
    """Time period comparison configuration."""

    base: dict[str, str] = Field(..., description="Base period: {start, end}")
    compare: dict[str, str] = Field(..., description="Compare period: {start, end}")
    metric: str = Field(..., description="Metric to compare")


class DrillDownConfig(BaseModel):
    """Hierarchical drill-down configuration."""

    level: str = Field(..., description="Starting level: zone, group, church, cell")
    include_children: bool = Field(default=True)
    max_depth: Optional[int] = Field(default=None, ge=1, le=5)


class DataQualityFilter(BaseModel):
    """Data validation filters."""

    verified_status: Optional[list[str]] = Field(
        default=None, description="For finance_entries: verified, reconciled, locked"
    )
    cell_report_status: Optional[list[str]] = Field(
        default=None, description="For cell_reports: submitted, reviewed, approved"
    )
    attendance_approved: Optional[bool] = Field(
        default=None, description="For attendance: only approved records"
    )


class VisualizationConfig(BaseModel):
    """Chart definition (format-agnostic)."""

    type: str = Field(
        ..., description="line_chart, bar_chart, pie_chart, heatmap, scatter"
    )
    x_axis: Optional[str] = Field(default=None, description="Field for X-axis")
    y_axis: Optional[str] = Field(default=None, description="Field for Y-axis")
    series: Optional[list[str]] = Field(
        default=None, description="Fields to group by for multiple series"
    )
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    colors: Optional[list[str]] = Field(
        default=None, description="Color palette for series"
    )


class PDFConfig(BaseModel):
    """PDF layout and styling configuration."""

    include_charts: bool = Field(default=True)
    chart_types: Optional[list[str]] = Field(
        default=None, description="Which chart types to include"
    )
    layout: str = Field(default="portrait", pattern="^(portrait|landscape)$")
    page_size: str = Field(default="A4", description="A4, Letter, etc.")
    margins: Optional[dict[str, int]] = Field(
        default_factory=lambda: {"top": 50, "bottom": 50, "left": 50, "right": 50}
    )
    chart_size: Optional[dict[str, int]] = Field(
        default_factory=lambda: {"width": 500, "height": 300}
    )
    sections: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Document sections configuration"
    )
    font_family: Optional[str] = Field(default="Helvetica")
    font_size: Optional[int] = Field(default=10)
    header_footer: Optional[dict[str, Any]] = Field(default=None)


# Query Request/Response Schemas

class ReportQueryRequest(BaseModel):
    """Complete query definition for flexible reports."""

    entity_type: str = Field(
        ...,
        description="finance_entries, attendance, cell_reports, people, services, batches, cells",
    )
    filters: dict[str, Any] = Field(default_factory=dict)
    aggregations: list[AggregationConfig] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[OrderByConfig] = Field(default_factory=list)
    compare_periods: Optional[PeriodComparison] = None
    drill_down: Optional[DrillDownConfig] = None
    data_quality: Optional[DataQualityFilter] = None
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    format: str = Field(default="json", pattern="^(json|csv|excel|pdf)$")
    visualization: Optional[VisualizationConfig] = None


class ReportQueryResponse(BaseModel):
    """Query results response."""

    results: list[dict[str, Any]]
    total: Optional[int] = None
    limit: int
    offset: int
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


# Dashboard Schemas

class DashboardRequest(BaseModel):
    """Predefined dashboard parameters."""

    org_unit_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    group_by: Optional[str] = Field(
        default=None, pattern="^(day|week|month|quarter|year)$"
    )
    include_children: bool = Field(default=False)


class DashboardResponse(BaseModel):
    """Dashboard data response."""

    data: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


# Export Schemas

class ExportJobRequest(BaseModel):
    """Export creation request."""

    query: Optional[ReportQueryRequest] = None
    template_id: Optional[UUID] = None
    format: str = Field(..., pattern="^(csv|excel|pdf)$")
    include_charts: bool = Field(default=False, description="For PDF exports")
    query_overrides: Optional[dict[str, Any]] = Field(
        default=None, description="Override template query parameters"
    )


class ExportJobResponse(BaseModel):
    """Export job status response."""

    id: UUID
    status: str
    format: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    total_rows: Optional[int] = None
    processed_rows: Optional[int] = None
    progress_percent: Optional[float] = Field(
        None, description="Progress percentage (0-100)"
    )
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# Template Schemas

class ReportTemplateRequest(BaseModel):
    """Template creation/update request."""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    query_definition: ReportQueryRequest
    visualization_config: Optional[VisualizationConfig] = None
    pdf_config: Optional[PDFConfig] = None
    is_shared: bool = Field(default=False)
    shared_with_org_units: Optional[list[UUID]] = Field(default=None)


class ReportTemplateResponse(BaseModel):
    """Template details response."""

    id: UUID
    name: str
    description: Optional[str]
    query_definition: dict[str, Any]
    visualization_config: Optional[dict[str, Any]]
    pdf_config: Optional[dict[str, Any]]
    is_shared: bool
    shared_with_org_units: Optional[list[UUID]]
    user_id: UUID
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ReportTemplateListResponse(BaseModel):
    """List of templates response."""

    items: list[ReportTemplateResponse]
    total: int


# Schedule Schemas

class ReportScheduleRequest(BaseModel):
    """Schedule creation request."""

    frequency: str = Field(..., pattern="^(daily|weekly|monthly|quarterly)$")
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    time: time
    recipients: list[str] = Field(..., min_length=1, description="Email addresses")
    query_overrides: Optional[dict[str, Any]] = Field(
        default=None, description="Override template query parameters"
    )


class ReportScheduleResponse(BaseModel):
    """Schedule details response."""

    id: UUID
    template_id: UUID
    frequency: str
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    time: str
    recipients: list[str]
    is_active: bool
    last_run_at: Optional[str]
    next_run_at: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ReportScheduleListResponse(BaseModel):
    """List of schedules response."""

    items: list[ReportScheduleResponse]
    total: int


