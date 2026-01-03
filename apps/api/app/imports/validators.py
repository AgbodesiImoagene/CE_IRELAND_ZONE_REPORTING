"""Validation rules for import data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.common.models import (
    People,
    OrgUnit,
    Service,
    Fund,
    Cell,
    Batch,
    PartnershipArm,
)


@dataclass
class ValidationError:
    """Validation error information."""

    row_number: int
    field: str
    error_type: str  # "required", "format", "reference", "constraint", "business"
    message: str
    original_value: Any
    suggestion: Optional[str] = None


def validate_required(value: Any, field_name: str) -> Optional[str]:
    """Validate that required field is not empty."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return f"Required field '{field_name}' is missing or empty"
    return None


def validate_email_format(value: Any) -> Optional[str]:
    """Validate email format."""
    if not value:
        return None  # Optional field

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, str(value)):
        return f"Invalid email format: {value}"
    return None


def validate_phone_format(value: Any) -> Optional[str]:
    """Validate phone format."""
    if not value:
        return None  # Optional field

    # Basic phone validation (at least 7 digits)
    cleaned = re.sub(r"[^\d+]", "", str(value))
    if len(cleaned) < 7:
        return f"Phone number too short: {value}"
    return None


def validate_date_range(value: date, min_date: Optional[date] = None, max_date: Optional[date] = None) -> Optional[str]:
    """Validate date is within range."""
    if not value:
        return None

    if min_date and value < min_date:
        return f"Date {value} is before minimum date {min_date}"
    if max_date and value > max_date:
        return f"Date {value} is after maximum date {max_date}"
    return None


def validate_string_length(value: str, max_length: int) -> Optional[str]:
    """Validate string length."""
    if value and len(value) > max_length:
        return f"String too long: {len(value)} > {max_length}"
    return None


def validate_org_unit_reference(
    db: Session, tenant_id: str, org_unit_id: str
) -> tuple[bool, Optional[str]]:
    """Validate org_unit_id exists."""
    try:
        from uuid import UUID
        org_uuid = UUID(org_unit_id)
        org = db.execute(
            select(OrgUnit).where(
                OrgUnit.id == org_uuid, OrgUnit.tenant_id == UUID(tenant_id)
            )
        ).scalar_one_or_none()
        if not org:
            return False, f"Org unit {org_unit_id} not found"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid org_unit_id format: {org_unit_id}"


def validate_service_reference(
    db: Session, tenant_id: str, service_id: str
) -> tuple[bool, Optional[str]]:
    """Validate service_id exists."""
    try:
        from uuid import UUID
        service_uuid = UUID(service_id)
        service = db.execute(
            select(Service).where(
                Service.id == service_uuid, Service.tenant_id == UUID(tenant_id)
            )
        ).scalar_one_or_none()
        if not service:
            return False, f"Service {service_id} not found"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid service_id format: {service_id}"


def validate_cell_reference(
    db: Session, tenant_id: str, cell_id: str
) -> tuple[bool, Optional[str]]:
    """Validate cell_id exists."""
    try:
        from uuid import UUID
        cell_uuid = UUID(cell_id)
        cell = db.execute(
            select(Cell).where(
                Cell.id == cell_uuid, Cell.tenant_id == UUID(tenant_id)
            )
        ).scalar_one_or_none()
        if not cell:
            return False, f"Cell {cell_id} not found"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid cell_id format: {cell_id}"


def validate_fund_reference(
    db: Session, tenant_id: str, fund_id: str
) -> tuple[bool, Optional[str]]:
    """Validate fund_id exists."""
    try:
        from uuid import UUID
        fund_uuid = UUID(fund_id)
        fund = db.execute(
            select(Fund).where(
                Fund.id == fund_uuid, Fund.tenant_id == UUID(tenant_id)
            )
        ).scalar_one_or_none()
        if not fund:
            return False, f"Fund {fund_id} not found"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid fund_id format: {fund_id}"


def validate_batch_reference(
    db: Session, tenant_id: str, batch_id: str
) -> tuple[bool, Optional[str]]:
    """Validate batch_id exists."""
    try:
        from uuid import UUID
        batch_uuid = UUID(batch_id)
        batch = db.execute(
            select(Batch).where(
                Batch.id == batch_uuid, Batch.tenant_id == UUID(tenant_id)
            )
        ).scalar_one_or_none()
        if not batch:
            return False, f"Batch {batch_id} not found"
        if batch.status == "locked":
            return False, f"Batch {batch_id} is locked"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid batch_id format: {batch_id}"


def validate_partnership_arm_reference(
    db: Session, tenant_id: str, partnership_arm_id: str
) -> tuple[bool, Optional[str]]:
    """Validate partnership_arm_id exists."""
    try:
        from uuid import UUID
        arm_uuid = UUID(partnership_arm_id)
        arm = db.execute(
            select(PartnershipArm).where(
                PartnershipArm.id == arm_uuid,
                PartnershipArm.tenant_id == UUID(tenant_id),
            )
        ).scalar_one_or_none()
        if not arm:
            return False, f"Partnership arm {partnership_arm_id} not found"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid partnership_arm_id format: {partnership_arm_id}"


def validate_unique_email(
    db: Session, tenant_id: str, email: str, exclude_person_id: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """Validate email is unique within tenant."""
    if not email:
        return True, None  # Optional field

    try:
        from uuid import UUID
        tenant_uuid = UUID(tenant_id)
        query = select(People).where(
            People.tenant_id == tenant_uuid, People.email == email.lower()
        )
        if exclude_person_id:
            query = query.where(People.id != UUID(exclude_person_id))
        existing = db.execute(query).scalar_one_or_none()
        if existing:
            return False, f"Email {email} already exists"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid tenant_id or email format"


def validate_unique_member_code(
    db: Session, tenant_id: str, member_code: str, exclude_person_id: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """Validate member_code is unique within tenant."""
    if not member_code:
        return True, None  # Optional field

    try:
        from uuid import UUID
        tenant_uuid = UUID(tenant_id)
        query = select(People).where(
            People.tenant_id == tenant_uuid, People.member_code == member_code
        )
        if exclude_person_id:
            query = query.where(People.id != UUID(exclude_person_id))
        existing = db.execute(query).scalar_one_or_none()
        if existing:
            return False, f"Member code {member_code} already exists"
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid tenant_id or member_code format"


def validate_business_rules(
    entity_type: str, row_data: dict[str, Any]
) -> list[ValidationError]:
    """Validate business rules specific to entity type."""
    errors = []

    if entity_type == "people":
        # Join date should not be in the future
        if "join_date" in row_data and row_data["join_date"]:
            if isinstance(row_data["join_date"], date):
                if row_data["join_date"] > date.today():
                    errors.append(
                        ValidationError(
                            row_number=row_data.get("_row_number", 0),
                            field="join_date",
                            error_type="business",
                            message="Join date cannot be in the future",
                            original_value=row_data["join_date"],
                        )
                    )

        # DOB should not be in the future
        if "dob" in row_data and row_data["dob"]:
            if isinstance(row_data["dob"], date):
                if row_data["dob"] > date.today():
                    errors.append(
                        ValidationError(
                            row_number=row_data.get("_row_number", 0),
                            field="dob",
                            error_type="business",
                            message="Date of birth cannot be in the future",
                            original_value=row_data["dob"],
                        )
                    )

    return errors

