"""Pydantic schemas for Finance module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Fund Schemas
class FundCreateRequest(BaseModel):
    """Request to create a fund."""

    name: str = Field(..., max_length=100)
    is_partnership: bool = Field(default=False)
    active: bool = Field(default=True)


class FundUpdateRequest(BaseModel):
    """Request to update a fund."""

    name: Optional[str] = Field(None, max_length=100)
    is_partnership: Optional[bool] = None
    active: Optional[bool] = None


class FundResponse(BaseModel):
    """Response with fund details."""

    id: UUID
    name: str
    is_partnership: bool
    active: bool
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Partnership Arm Schemas
class PartnershipArmCreateRequest(BaseModel):
    """Request to create a partnership arm."""

    name: str = Field(..., max_length=200)
    active_from: date
    active_to: Optional[date] = None
    active: bool = Field(default=True)


class PartnershipArmUpdateRequest(BaseModel):
    """Request to update a partnership arm."""

    name: Optional[str] = Field(None, max_length=200)
    active_from: Optional[date] = None
    active_to: Optional[date] = None
    active: Optional[bool] = None


class PartnershipArmResponse(BaseModel):
    """Response with partnership arm details."""

    id: UUID
    name: str
    active_from: date
    active_to: Optional[date]
    active: bool
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Batch Schemas
class BatchCreateRequest(BaseModel):
    """Request to create a batch."""

    org_unit_id: UUID
    service_id: Optional[UUID] = None


class BatchUpdateRequest(BaseModel):
    """Request to update a batch."""

    service_id: Optional[UUID] = None


class BatchLockRequest(BaseModel):
    """Request to lock a batch (requires dual verification)."""

    reason: Optional[str] = Field(None, max_length=500)


class BatchUnlockRequest(BaseModel):
    """Request to unlock a batch (requires dual authorization)."""

    reason: str = Field(..., min_length=10, max_length=500)


class BatchResponse(BaseModel):
    """Response with batch details."""

    id: UUID
    org_unit_id: UUID
    service_id: Optional[UUID]
    status: str
    locked_by: Optional[UUID]
    locked_at: Optional[str]
    verified_by_1: Optional[UUID]
    verified_by_2: Optional[UUID]
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Finance Entry Schemas
class FinanceEntryCreateRequest(BaseModel):
    """Request to create a finance entry."""

    org_unit_id: UUID
    batch_id: Optional[UUID] = None
    service_id: Optional[UUID] = None
    fund_id: UUID
    partnership_arm_id: Optional[UUID] = None
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="EUR", max_length=3)
    method: str = Field(
        ..., pattern="^(cash|kingspay|bank_transfer|pos|cheque|other)$"
    )
    person_id: Optional[UUID] = None
    cell_id: Optional[UUID] = None
    external_giver_name: Optional[str] = None
    reference: Optional[str] = Field(None, max_length=200)
    comment: Optional[str] = None
    transaction_date: date


class FinanceEntryUpdateRequest(BaseModel):
    """Request to update a finance entry."""

    fund_id: Optional[UUID] = None
    partnership_arm_id: Optional[UUID] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    method: Optional[str] = Field(
        None, pattern="^(cash|kingspay|bank_transfer|pos|cheque|other)$"
    )
    person_id: Optional[UUID] = None
    cell_id: Optional[UUID] = None
    external_giver_name: Optional[str] = None
    reference: Optional[str] = Field(None, max_length=200)
    comment: Optional[str] = None
    transaction_date: Optional[date] = None


class FinanceEntryVerifyRequest(BaseModel):
    """Request to verify a finance entry."""

    verified_status: str = Field(
        ..., pattern="^(verified|reconciled|locked)$"
    )


class FinanceEntryResponse(BaseModel):
    """Response with finance entry details."""

    id: UUID
    org_unit_id: UUID
    batch_id: Optional[UUID]
    service_id: Optional[UUID]
    fund_id: UUID
    partnership_arm_id: Optional[UUID]
    amount: Decimal
    currency: str
    method: str
    person_id: Optional[UUID]
    cell_id: Optional[UUID]
    external_giver_name: Optional[str]
    reference: Optional[str]
    comment: Optional[str]
    verified_status: str
    source_type: str
    source_id: Optional[UUID]
    transaction_date: date
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Partnership Schemas
class PartnershipCreateRequest(BaseModel):
    """Request to create a partnership."""

    person_id: UUID
    fund_id: UUID
    partnership_arm_id: Optional[UUID] = None
    cadence: str = Field(
        ..., pattern="^(weekly|monthly|quarterly|annual)$"
    )
    start_date: date
    end_date: Optional[date] = None
    target_amount: Optional[Decimal] = Field(None, ge=0)
    status: str = Field(default="active", pattern="^(active|paused|ended)$")


class PartnershipUpdateRequest(BaseModel):
    """Request to update a partnership."""

    partnership_arm_id: Optional[UUID] = None
    cadence: Optional[str] = Field(
        None, pattern="^(weekly|monthly|quarterly|annual)$"
    )
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_amount: Optional[Decimal] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(active|paused|ended)$")


class PartnershipResponse(BaseModel):
    """Response with partnership details."""

    id: UUID
    person_id: UUID
    fund_id: UUID
    partnership_arm_id: Optional[UUID]
    cadence: str
    start_date: date
    end_date: Optional[date]
    target_amount: Optional[Decimal]
    status: str
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


class PartnershipFulfilmentResponse(BaseModel):
    """Response with partnership fulfilment details."""

    partnership_id: UUID
    target_amount: Optional[Decimal]
    fulfilled_amount: Decimal
    fulfilment_percentage: Optional[Decimal]
    cadence: str
    start_date: date
    end_date: Optional[date]
    entries_count: int

