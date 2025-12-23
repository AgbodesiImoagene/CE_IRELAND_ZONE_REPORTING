"""Pydantic schemas for Registry module."""

from __future__ import annotations

from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# People Schemas
class PeopleCreateRequest(BaseModel):
    """Request to create a person."""

    org_unit_id: UUID
    title: Optional[str] = Field(None, max_length=20)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    alias: Optional[str] = Field(None, max_length=100)
    dob: Optional[date] = None
    gender: str = Field(..., pattern="^(male|female|other)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    town: Optional[str] = Field(None, max_length=100)
    county: Optional[str] = Field(None, max_length=100)
    eircode: Optional[str] = Field(None, max_length=10)
    marital_status: Optional[str] = Field(
        None, pattern="^(single|married|divorced|widowed|separated)$"
    )
    consent_contact: bool = Field(default=True)
    consent_data_storage: bool = Field(default=True)
    # Membership fields
    membership_status: Optional[str] = Field(
        None, pattern="^(visitor|regular|member|partner)$"
    )
    join_date: Optional[date] = None
    foundation_completed: bool = Field(default=False)
    baptism_date: Optional[date] = None


class PeopleUpdateRequest(BaseModel):
    """Request to update a person."""

    title: Optional[str] = Field(None, max_length=20)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    alias: Optional[str] = Field(None, max_length=100)
    dob: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    town: Optional[str] = Field(None, max_length=100)
    county: Optional[str] = Field(None, max_length=100)
    eircode: Optional[str] = Field(None, max_length=10)
    marital_status: Optional[str] = Field(
        None, pattern="^(single|married|divorced|widowed|separated)$"
    )
    consent_contact: Optional[bool] = None
    consent_data_storage: Optional[bool] = None


class PeopleResponse(BaseModel):
    """Response with person details."""

    id: UUID
    org_unit_id: UUID
    member_code: Optional[str]
    title: Optional[str]
    first_name: str
    last_name: str
    alias: Optional[str]
    dob: Optional[date]
    gender: str
    email: Optional[str]
    phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    town: Optional[str]
    county: Optional[str]
    eircode: Optional[str]
    marital_status: Optional[str]
    consent_contact: bool
    consent_data_storage: bool
    membership_status: Optional[str] = None
    join_date: Optional[date] = None
    foundation_completed: Optional[bool] = None
    baptism_date: Optional[date] = None
    cell_id: Optional[UUID] = None
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


class PeopleMergeRequest(BaseModel):
    """Request to merge two people records."""

    source_person_id: UUID  # Person to merge from (will be deleted)
    target_person_id: UUID  # Person to merge into (will be kept)
    reason: str = Field(..., min_length=10, max_length=500)


# First-Timers Schemas
class FirstTimerCreateRequest(BaseModel):
    """Request to create a first-timer."""

    service_id: UUID
    person_id: Optional[UUID] = None  # If already a person record
    # If not a person, include these fields
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    source: Optional[str] = Field(None, max_length=200)  # inviter/source
    notes: Optional[str] = None


class FirstTimerUpdateRequest(BaseModel):
    """Request to update a first-timer."""

    status: Optional[str] = Field(None, pattern="^(New|Contacted|Returned|Member)$")
    source: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class FirstTimerResponse(BaseModel):
    """Response with first-timer details."""

    id: UUID
    person_id: Optional[UUID]
    service_id: UUID
    source: Optional[str]
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


class FirstTimerConvertRequest(BaseModel):
    """Request to convert a first-timer to a member."""

    # Person details (if not already a person)
    org_unit_id: UUID
    title: Optional[str] = Field(None, max_length=20)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    dob: Optional[date] = None
    gender: str = Field(..., pattern="^(male|female|other)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    town: Optional[str] = Field(None, max_length=100)
    county: Optional[str] = Field(None, max_length=100)
    eircode: Optional[str] = Field(None, max_length=10)
    marital_status: Optional[str] = Field(
        None, pattern="^(single|married|divorced|widowed|separated)$"
    )
    consent_contact: bool = Field(default=True)
    consent_data_storage: bool = Field(default=True)


# Services Schemas
class ServiceCreateRequest(BaseModel):
    """Request to create a service."""

    org_unit_id: UUID
    name: str = Field(..., max_length=50)  # Sunday, Midweek, Special or text
    service_date: date
    service_time: Optional[time] = None


class ServiceResponse(BaseModel):
    """Response with service details."""

    id: UUID
    org_unit_id: UUID
    name: str
    service_date: date
    service_time: Optional[time]

    model_config = {
        "from_attributes": True,
    }


# Attendance Schemas
class AttendanceCreateRequest(BaseModel):
    """Request to create attendance record."""

    service_id: UUID
    men_count: int = Field(default=0, ge=0)
    women_count: int = Field(default=0, ge=0)
    teens_count: int = Field(default=0, ge=0)
    kids_count: int = Field(default=0, ge=0)
    first_timers_count: int = Field(default=0, ge=0)
    new_converts_count: int = Field(default=0, ge=0)
    total_attendance: Optional[int] = Field(None, ge=0)  # Auto-calculated if not provided
    notes: Optional[str] = None


class AttendanceUpdateRequest(BaseModel):
    """Request to update attendance record."""

    men_count: Optional[int] = Field(None, ge=0)
    women_count: Optional[int] = Field(None, ge=0)
    teens_count: Optional[int] = Field(None, ge=0)
    kids_count: Optional[int] = Field(None, ge=0)
    first_timers_count: Optional[int] = Field(None, ge=0)
    new_converts_count: Optional[int] = Field(None, ge=0)
    total_attendance: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    """Response with attendance details."""

    id: UUID
    service_id: UUID
    men_count: int
    women_count: int
    teens_count: int
    kids_count: int
    first_timers_count: int
    new_converts_count: int
    total_attendance: int
    notes: Optional[str]
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Departments Schemas
class DepartmentCreateRequest(BaseModel):
    """Request to create a department."""

    org_unit_id: UUID
    name: str = Field(..., max_length=200)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class DepartmentUpdateRequest(BaseModel):
    """Request to update a department."""

    name: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")


class DepartmentResponse(BaseModel):
    """Response with department details."""

    id: UUID
    org_unit_id: UUID
    name: str
    status: str
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True,
    }


# Department Roles Schemas
class DepartmentRoleAssignRequest(BaseModel):
    """Request to assign a person to a department."""

    person_id: UUID
    role: str = Field(..., pattern="^(leader|member)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class DepartmentRoleResponse(BaseModel):
    """Response with department role assignment details."""

    id: UUID
    dept_id: UUID
    person_id: UUID
    role: str
    start_date: Optional[date]
    end_date: Optional[date]

    model_config = {
        "from_attributes": True,
    }

