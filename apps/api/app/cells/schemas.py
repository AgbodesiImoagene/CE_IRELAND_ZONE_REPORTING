"""Pydantic schemas for Cells module."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Cell Schemas
class CellCreateRequest(BaseModel):
    """Request to create a cell."""

    org_unit_id: UUID
    name: str = Field(..., max_length=200)
    leader_id: Optional[UUID] = None
    assistant_leader_id: Optional[UUID] = None
    venue: Optional[str] = Field(None, max_length=200)
    meeting_day: Optional[str] = Field(
        None, pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$"
    )
    meeting_time: Optional[time] = None
    status: str = Field(default="active", pattern="^(active|inactive)$")


class CellUpdateRequest(BaseModel):
    """Request to update a cell."""

    name: Optional[str] = Field(None, max_length=200)
    leader_id: Optional[UUID] = None
    assistant_leader_id: Optional[UUID] = None
    venue: Optional[str] = Field(None, max_length=200)
    meeting_day: Optional[str] = Field(
        None, pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$"
    )
    meeting_time: Optional[time] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")


class CellResponse(BaseModel):
    """Response with cell details."""

    id: UUID
    org_unit_id: UUID
    name: str
    leader_id: Optional[UUID]
    assistant_leader_id: Optional[UUID]
    venue: Optional[str]
    meeting_day: Optional[str]
    meeting_time: Optional[time]
    status: str
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Cell Report Schemas
class CellReportCreateRequest(BaseModel):
    """Request to create a cell report."""

    cell_id: UUID
    report_date: date
    report_time: Optional[time] = None
    attendance: int = Field(default=0, ge=0)
    first_timers: int = Field(default=0, ge=0)
    new_converts: int = Field(default=0, ge=0)
    testimonies: Optional[str] = None
    offerings_total: Decimal = Field(default=Decimal("0.00"), ge=0)
    meeting_type: str = Field(
        ..., pattern="^(prayer_planning|bible_study|outreach)$"
    )
    notes: Optional[str] = None


class CellReportUpdateRequest(BaseModel):
    """Request to update a cell report."""

    report_date: Optional[date] = None
    report_time: Optional[time] = None
    attendance: Optional[int] = Field(None, ge=0)
    first_timers: Optional[int] = Field(None, ge=0)
    new_converts: Optional[int] = Field(None, ge=0)
    testimonies: Optional[str] = None
    offerings_total: Optional[Decimal] = Field(None, ge=0)
    meeting_type: Optional[str] = Field(
        None, pattern="^(prayer_planning|bible_study|outreach)$"
    )
    notes: Optional[str] = None


class CellReportApproveRequest(BaseModel):
    """Request to approve/review a cell report."""

    status: str = Field(..., pattern="^(reviewed|approved)$")


class CellReportResponse(BaseModel):
    """Response with cell report details."""

    id: UUID
    cell_id: UUID
    report_date: date
    report_time: Optional[time]
    attendance: int
    first_timers: int
    new_converts: int
    testimonies: Optional[str]
    offerings_total: Decimal
    meeting_type: str
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


