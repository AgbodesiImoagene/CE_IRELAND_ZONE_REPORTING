"""Entity-specific processors for import operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.common.models import (
    People,
    Membership,
    FirstTimer,
    Service,
    Attendance,
    Cell,
    CellReport,
    FinanceEntry,
    Fund,
    Batch,
    PartnershipArm,
)
from app.registry.service import (
    PeopleService,
    ServiceService,
    FirstTimerService,
    AttendanceService,
)
from app.cells.service import CellService, CellReportService
from app.finance.service import FinanceEntryService
from app.imports.coercers import coerce_value, CoercionResult
from app.imports.validators import (
    validate_required,
    validate_email_format,
    validate_phone_format,
    validate_org_unit_reference,
    validate_service_reference,
    validate_cell_reference,
    validate_fund_reference,
    validate_batch_reference,
    validate_partnership_arm_reference,
    validate_unique_email,
    validate_unique_member_code,
    ValidationError,
)


@dataclass
class ProcessResult:
    """Result of processing a row."""

    success: bool
    entity_id: Optional[UUID] = None
    errors: list[ValidationError] = None
    warnings: list[str] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class EntityProcessor(ABC):
    """Abstract base class for entity processors."""

    @abstractmethod
    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a single row."""
        pass

    @abstractmethod
    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate foreign key references."""
        pass

    def requires_org_unit(self) -> bool:
        """
        Check if this processor requires org_unit_id.

        Returns:
            True if org_unit_id is required, False otherwise
        """
        return False


class PeopleProcessor(EntityProcessor):
    """Processor for People entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a People row."""
        errors = []
        warnings = []

        # Map row data to People fields
        mapped_data = {}
        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Extract required fields
        first_name = mapped_data.get("first_name", "").strip()
        last_name = mapped_data.get("last_name", "").strip()
        gender = mapped_data.get("gender", "").strip()

        # Validate required fields
        if not first_name:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="first_name",
                    error_type="required",
                    message="First name is required",
                    original_value=mapped_data.get("first_name"),
                )
            )
        if not last_name:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="last_name",
                    error_type="required",
                    message="Last name is required",
                    original_value=mapped_data.get("last_name"),
                )
            )
        if not gender:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="gender",
                    error_type="required",
                    message="Gender is required",
                    original_value=mapped_data.get("gender"),
                )
            )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Coerce values
        from app.common.models import Gender, MaritalStatus

        # Coerce gender
        gender_result = coerce_value(gender, "enum", {"enum_class": Gender})
        if not gender_result.success:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="gender",
                    error_type="coercion",
                    message=gender_result.error or "Invalid gender",
                    original_value=gender,
                )
            )
        else:
            gender = gender_result.coerced_value

        # Coerce email
        email = mapped_data.get("email", "").strip()
        if email:
            email_result = coerce_value(email, "email")
            if email_result.success:
                email = email_result.coerced_value
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="email",
                        error_type="coercion",
                        message=email_result.error or "Invalid email",
                        original_value=email,
                    )
                )

        # Coerce phone
        phone = mapped_data.get("phone", "").strip()
        if phone:
            phone_result = coerce_value(phone, "phone")
            if phone_result.success:
                phone = phone_result.coerced_value
                if phone_result.warnings:
                    warnings.extend(phone_result.warnings)

        # Coerce DOB
        dob = None
        if mapped_data.get("dob"):
            dob_result = coerce_value(mapped_data.get("dob"), "date")
            if dob_result.success:
                dob = dob_result.coerced_value
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="dob",
                        error_type="coercion",
                        message=dob_result.error or "Invalid date",
                        original_value=mapped_data.get("dob"),
                    )
                )

        # Coerce marital status
        marital_status = None
        if mapped_data.get("marital_status"):
            marital_result = coerce_value(
                mapped_data.get("marital_status"), "enum", {"enum_class": MaritalStatus}
            )
            if marital_result.success:
                marital_status = marital_result.coerced_value

        # Get org_unit_id (required)
        if not org_unit_id:
            # Try to get from row
            org_unit_id_str = mapped_data.get("org_unit_id")
            if org_unit_id_str:
                try:
                    org_unit_id = UUID(org_unit_id_str)
                except (ValueError, TypeError):
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="org_unit_id",
                            error_type="reference",
                            message="Invalid org_unit_id format",
                            original_value=org_unit_id_str,
                        )
                    )
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="required",
                        message="org_unit_id is required",
                        original_value=None,
                    )
                )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Check for existing person (for update mode) - do this BEFORE validation
        existing_person = None
        if mode == "update_existing":
            # Try to find by email or member_code
            if email:
                existing_person = db.execute(
                    select(People).where(
                        People.tenant_id == tenant_id, People.email == email.lower()
                    )
                ).scalar_one_or_none()

            if not existing_person and mapped_data.get("member_code"):
                existing_person = db.execute(
                    select(People).where(
                        People.tenant_id == tenant_id,
                        People.member_code == mapped_data.get("member_code"),
                    )
                ).scalar_one_or_none()

        # Validate references (pass existing_person_id to exclude from unique checks)
        exclude_person_id = str(existing_person.id) if existing_person else None
        ref_errors = self.validate_references(
            db, mapped_data, str(tenant_id), exclude_person_id=exclude_person_id
        )
        if ref_errors:
            errors.extend(ref_errors)
            return ProcessResult(success=False, errors=errors)

        try:
            if existing_person and mode == "update_existing":
                # Update existing person
                existing_person.first_name = first_name
                existing_person.last_name = last_name
                existing_person.gender = gender
                if email:
                    existing_person.email = email.lower()
                if phone:
                    existing_person.phone = phone
                if dob:
                    existing_person.dob = dob
                if marital_status:
                    existing_person.marital_status = marital_status
                # Update other fields
                for field in [
                    "title",
                    "alias",
                    "address_line1",
                    "address_line2",
                    "town",
                    "county",
                    "eircode",
                ]:
                    if field in mapped_data:
                        setattr(existing_person, field, mapped_data[field])

                existing_person.updated_by = user_id
                db.flush()
                return ProcessResult(
                    success=True, entity_id=existing_person.id, warnings=warnings
                )
            else:
                # Create new person
                person = PeopleService.create_person(
                    db=db,
                    creator_id=user_id,
                    tenant_id=tenant_id,
                    org_unit_id=org_unit_id,
                    first_name=first_name,
                    last_name=last_name,
                    gender=gender,
                    title=mapped_data.get("title"),
                    alias=mapped_data.get("alias"),
                    dob=dob,
                    email=email,
                    phone=phone,
                    address_line1=mapped_data.get("address_line1"),
                    address_line2=mapped_data.get("address_line2"),
                    town=mapped_data.get("town"),
                    county=mapped_data.get("county"),
                    eircode=mapped_data.get("eircode"),
                    marital_status=marital_status,
                )
                return ProcessResult(
                    success=True, entity_id=person.id, warnings=warnings
                )
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="general",
                    error_type="constraint",
                    message=f"Failed to create/update person: {str(e)}",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate foreign key references for People."""
        errors = []

        # Validate org_unit_id
        if "org_unit_id" in row:
            valid, error_msg = validate_org_unit_reference(
                db, str(tenant_id), str(row["org_unit_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="reference",
                        message=error_msg or "Org unit not found",
                        original_value=row["org_unit_id"],
                    )
                )

        # Validate unique email (exclude existing person if updating)
        if "email" in row and row["email"]:
            valid, error_msg = validate_unique_email(
                db, str(tenant_id), row["email"], exclude_person_id=exclude_person_id
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="email",
                        error_type="constraint",
                        message=error_msg or "Email already exists",
                        original_value=row["email"],
                    )
                )

        # Validate unique member_code (exclude existing person if updating)
        if "member_code" in row and row["member_code"]:
            valid, error_msg = validate_unique_member_code(
                db,
                str(tenant_id),
                row["member_code"],
                exclude_person_id=exclude_person_id,
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="member_code",
                        error_type="constraint",
                        message=error_msg or "Member code already exists",
                        original_value=row["member_code"],
                    )
                )

        return errors

    def requires_org_unit(self) -> bool:
        """People processor requires org_unit_id."""
        return True


class MembershipProcessor(EntityProcessor):
    """Processor for Membership entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a Membership row."""
        # Membership is typically created/updated through People processor
        # This processor can handle standalone membership updates
        errors = []
        mapped_data = {}

        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Find person by email or member_code
        person = None
        if "email" in mapped_data and mapped_data["email"]:
            person = db.execute(
                select(People).where(
                    People.tenant_id == tenant_id,
                    People.email == mapped_data["email"].lower(),
                )
            ).scalar_one_or_none()

        if not person and "member_code" in mapped_data:
            person = db.execute(
                select(People).where(
                    People.tenant_id == tenant_id,
                    People.member_code == mapped_data["member_code"],
                )
            ).scalar_one_or_none()

        if not person:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="person",
                    error_type="reference",
                    message="Person not found",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

        # Create or update membership
        membership = db.get(Membership, person.id)
        if not membership:
            membership = Membership(person_id=person.id)
            db.add(membership)

        # Update fields
        if "status" in mapped_data:
            from app.common.models import MembershipStatus
            status_result = coerce_value(
                mapped_data["status"], "enum", {"enum_class": MembershipStatus}
            )
            if status_result.success:
                membership.status = status_result.coerced_value

        if "join_date" in mapped_data:
            join_date_result = coerce_value(mapped_data["join_date"], "date")
            if join_date_result.success:
                membership.join_date = join_date_result.coerced_value

        if "foundation_completed" in mapped_data:
            foundation_result = coerce_value(mapped_data["foundation_completed"], "boolean")
            if foundation_result.success:
                membership.foundation_completed = foundation_result.coerced_value

        if "baptism_date" in mapped_data:
            baptism_result = coerce_value(mapped_data["baptism_date"], "date")
            if baptism_result.success:
                membership.baptism_date = baptism_result.coerced_value

        db.flush()
        return ProcessResult(success=True, entity_id=person.id)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for Membership."""
        return []  # Handled in process_row

    def requires_org_unit(self) -> bool:
        """Membership processor does not require org_unit_id."""
        return False


class FirstTimerProcessor(EntityProcessor):
    """Processor for FirstTimer entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a FirstTimer row."""
        errors = []
        mapped_data = {}

        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Extract required fields
        service_id_str = mapped_data.get("service_id")
        if not service_id_str:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="required",
                    message="service_id is required",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

        try:
            service_id = UUID(service_id_str)
        except (ValueError, TypeError):
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="reference",
                    message="Invalid service_id format",
                    original_value=service_id_str,
                )
            )
            return ProcessResult(success=False, errors=errors)

        # Validate service exists
        service = db.execute(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if not service:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="reference",
                    message=f"Service {service_id} not found",
                    original_value=service_id_str,
                )
            )
            return ProcessResult(success=False, errors=errors)

        # Coerce status if provided
        status = "New"
        if mapped_data.get("status"):
            from app.common.models import FirstTimerStatus
            status_result = coerce_value(
                mapped_data["status"], "enum", {"enum_class": FirstTimerStatus}
            )
            if status_result.success:
                status = status_result.coerced_value

        # Find person if email or member_code provided
        person_id = None
        if mapped_data.get("email"):
            person = db.execute(
                select(People).where(
                    People.tenant_id == tenant_id,
                    People.email == mapped_data["email"].lower(),
                )
            ).scalar_one_or_none()
            if person:
                person_id = person.id
        elif mapped_data.get("member_code"):
            person = db.execute(
                select(People).where(
                    People.tenant_id == tenant_id,
                    People.member_code == mapped_data["member_code"],
                )
            ).scalar_one_or_none()
            if person:
                person_id = person.id

        try:
            first_timer = FirstTimerService.create_first_timer(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                service_id=service_id,
                person_id=person_id,
                source=mapped_data.get("source"),
                notes=mapped_data.get("notes"),
            )
            # Update status if different from default
            if status != "New":
                FirstTimerService.update_first_timer_status(
                    db, user_id, tenant_id, first_timer.id, status
                )
            return ProcessResult(success=True, entity_id=first_timer.id)
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="general",
                    error_type="constraint",
                    message=f"Failed to create first timer: {str(e)}",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for FirstTimer."""
        errors = []
        if "service_id" in row and row["service_id"]:
            valid, error_msg = validate_service_reference(
                db, str(tenant_id), str(row["service_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="service_id",
                        error_type="reference",
                        message=error_msg or "Service not found",
                        original_value=row["service_id"],
                    )
                )
        return errors

    def requires_org_unit(self) -> bool:
        """FirstTimer processor does not require org_unit_id."""
        return False


class ServiceProcessor(EntityProcessor):
    """Processor for Service entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a Service row."""
        errors = []
        mapped_data = {}

        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Extract required fields
        name = mapped_data.get("name", "").strip()
        service_date_str = mapped_data.get("service_date")

        if not name:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="name",
                    error_type="required",
                    message="Service name is required",
                    original_value=mapped_data.get("name"),
                )
            )

        if not service_date_str:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_date",
                    error_type="required",
                    message="Service date is required",
                    original_value=None,
                )
            )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Coerce service_date
        service_date_result = coerce_value(service_date_str, "date")
        if not service_date_result.success:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_date",
                    error_type="coercion",
                    message=service_date_result.error or "Invalid date",
                    original_value=service_date_str,
                )
            )
            return ProcessResult(success=False, errors=errors)
        service_date = service_date_result.coerced_value

        # Coerce service_time if provided
        service_time = None
        if mapped_data.get("service_time"):
            time_result = coerce_value(mapped_data["service_time"], "time")
            if time_result.success:
                service_time = time_result.coerced_value

        # Get org_unit_id (required)
        if not org_unit_id:
            org_unit_id_str = mapped_data.get("org_unit_id")
            if org_unit_id_str:
                try:
                    org_unit_id = UUID(org_unit_id_str)
                except (ValueError, TypeError):
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="org_unit_id",
                            error_type="reference",
                            message="Invalid org_unit_id format",
                            original_value=org_unit_id_str,
                        )
                    )
                    return ProcessResult(success=False, errors=errors)
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="required",
                        message="org_unit_id is required",
                        original_value=None,
                    )
                )
                return ProcessResult(success=False, errors=errors)

        # Validate org_unit exists
        ref_errors = self.validate_references(
            db, mapped_data, tenant_id, exclude_person_id=None
        )
        if ref_errors:
            errors.extend(ref_errors)
            return ProcessResult(success=False, errors=errors)

        try:
            service = ServiceService.create_service(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                org_unit_id=org_unit_id,
                name=name,
                service_date=service_date,
                service_time=service_time,
            )
            return ProcessResult(success=True, entity_id=service.id)
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="general",
                    error_type="constraint",
                    message=f"Failed to create service: {str(e)}",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for Service."""
        errors = []
        if "org_unit_id" in row and row["org_unit_id"]:
            valid, error_msg = validate_org_unit_reference(
                db, str(tenant_id), str(row["org_unit_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="reference",
                        message=error_msg or "Org unit not found",
                        original_value=row["org_unit_id"],
                    )
                )
        return errors


class AttendanceProcessor(EntityProcessor):
    """Processor for Attendance entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process an Attendance row."""
        errors = []
        mapped_data = {}

        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Extract required fields
        service_id_str = mapped_data.get("service_id")
        if not service_id_str:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="required",
                    message="service_id is required",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

        try:
            service_id = UUID(service_id_str)
        except (ValueError, TypeError):
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="reference",
                    message="Invalid service_id format",
                    original_value=service_id_str,
                )
            )
            return ProcessResult(success=False, errors=errors)

        # Validate service exists
        service = db.execute(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if not service:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="service_id",
                    error_type="reference",
                    message=f"Service {service_id} not found",
                    original_value=service_id_str,
                )
            )
            return ProcessResult(success=False, errors=errors)

        # Coerce counts (default to 0)
        def get_count(field_name: str, default: int = 0) -> int:
            value = mapped_data.get(field_name, default)
            if value == "" or value is None:
                return default
            result = coerce_value(value, "integer")
            return result.coerced_value if result.success else default

        men_count = get_count("men_count", 0)
        women_count = get_count("women_count", 0)
        teens_count = get_count("teens_count", 0)
        kids_count = get_count("kids_count", 0)
        first_timers_count = get_count("first_timers_count", 0)
        new_converts_count = get_count("new_converts_count", 0)

        # Get total_attendance if provided, otherwise calculate
        total_attendance = None
        if mapped_data.get("total_attendance") or mapped_data.get("attendance_count"):
            total_str = mapped_data.get("total_attendance") or mapped_data.get(
                "attendance_count"
            )
            total_result = coerce_value(total_str, "integer")
            if total_result.success:
                total_attendance = total_result.coerced_value

        try:
            attendance = AttendanceService.create_attendance(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                service_id=service_id,
                men_count=men_count,
                women_count=women_count,
                teens_count=teens_count,
                kids_count=kids_count,
                first_timers_count=first_timers_count,
                new_converts_count=new_converts_count,
                total_attendance=total_attendance,
                notes=mapped_data.get("notes"),
            )
            return ProcessResult(success=True, entity_id=attendance.id)
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="general",
                    error_type="constraint",
                    message=f"Failed to create attendance: {str(e)}",
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for Attendance."""
        errors = []
        if "service_id" in row and row["service_id"]:
            valid, error_msg = validate_service_reference(
                db, str(tenant_id), str(row["service_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="service_id",
                        error_type="reference",
                        message=error_msg or "Service not found",
                        original_value=row["service_id"],
                    )
                )
        return errors

    def requires_org_unit(self) -> bool:
        """Attendance processor does not require org_unit_id."""
        return False


class CellProcessor(EntityProcessor):
    """Processor for Cell entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a Cell row."""
        errors = []
        warnings = []

        # Map row data to Cell fields
        mapped_data = {}
        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Get required fields
        name = mapped_data.get("name", "").strip()
        if not name:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="name",
                    error_type="required",
                    message="name is required",
                    original_value=None,
                )
            )

        # Get org_unit_id (required)
        if not org_unit_id:
            org_unit_id_str = mapped_data.get("org_unit_id")
            if org_unit_id_str:
                try:
                    org_unit_id = UUID(org_unit_id_str)
                except (ValueError, TypeError):
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="org_unit_id",
                            error_type="reference",
                            message="Invalid org_unit_id format",
                            original_value=org_unit_id_str,
                        )
                    )
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="required",
                        message="org_unit_id is required",
                        original_value=None,
                    )
                )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Validate references
        ref_errors = self.validate_references(
            db, mapped_data, tenant_id, exclude_person_id=None
        )
        if ref_errors:
            errors.extend(ref_errors)
            return ProcessResult(success=False, errors=errors)

        # Coerce values
        from app.common.models.base import MeetingDay

        leader_id = None
        if mapped_data.get("leader_id"):
            try:
                leader_id = UUID(str(mapped_data.get("leader_id")))
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="leader_id",
                        error_type="reference",
                        message="Invalid leader_id format",
                        original_value=mapped_data.get("leader_id"),
                    )
                )

        assistant_leader_id = None
        if mapped_data.get("assistant_leader_id"):
            try:
                assistant_leader_id = UUID(
                    str(mapped_data.get("assistant_leader_id"))
                )
            except (ValueError, TypeError):
                pass  # Optional field

        meeting_day = None
        if mapped_data.get("meeting_day"):
            meeting_day_result = coerce_value(
                mapped_data.get("meeting_day"),
                "enum",
                {"enum_class": MeetingDay},
            )
            if meeting_day_result.success:
                meeting_day = meeting_day_result.coerced_value
            # meeting_day is optional, so don't add error if coercion fails

        meeting_time = None
        if mapped_data.get("meeting_time"):
            time_result = coerce_value(mapped_data.get("meeting_time"), "time")
            if time_result.success:
                meeting_time = time_result.coerced_value

        status = mapped_data.get("status", "active").strip() or "active"
        venue = mapped_data.get("venue", "").strip() or None

        if errors:
            return ProcessResult(success=False, errors=errors)

        try:
            cell = CellService.create_cell(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                org_unit_id=org_unit_id,
                name=name,
                leader_id=leader_id,
                assistant_leader_id=assistant_leader_id,
                venue=venue,
                meeting_day=meeting_day,
                meeting_time=meeting_time,
                status=status,
            )
            return ProcessResult(success=True, entity_id=cell.id, warnings=warnings)
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="",
                    error_type="business",
                    message=str(e),
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for Cell."""
        errors = []

        if "leader_id" in row and row["leader_id"]:
            try:
                leader_uuid = UUID(str(row["leader_id"]))
                leader = db.get(People, leader_uuid)
                if not leader or str(leader.tenant_id) != str(tenant_id):
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="leader_id",
                            error_type="reference",
                            message="Leader not found",
                            original_value=row["leader_id"],
                        )
                    )
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="leader_id",
                        error_type="reference",
                        message="Invalid leader_id format",
                        original_value=row["leader_id"],
                    )
                )

        if "assistant_leader_id" in row and row["assistant_leader_id"]:
            try:
                assistant_uuid = UUID(str(row["assistant_leader_id"]))
                assistant = db.get(People, assistant_uuid)
                if not assistant or assistant.tenant_id != tenant_id:
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="assistant_leader_id",
                            error_type="reference",
                            message="Assistant leader not found",
                            original_value=row["assistant_leader_id"],
                        )
                    )
            except (ValueError, TypeError):
                pass  # Optional field

        return errors

    def requires_org_unit(self) -> bool:
        """Cell processor requires org_unit_id."""
        return True


class CellReportProcessor(EntityProcessor):
    """Processor for CellReport entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a CellReport row."""
        errors = []
        warnings = []

        # Map row data to CellReport fields
        mapped_data = {}
        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Get required fields
        cell_id_str = mapped_data.get("cell_id")
        cell_id = None
        if not cell_id_str:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="cell_id",
                    error_type="required",
                    message="cell_id is required",
                    original_value=None,
                )
            )
        else:
            try:
                cell_id = UUID(str(cell_id_str))
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="cell_id",
                        error_type="reference",
                        message="Invalid cell_id format",
                        original_value=cell_id_str,
                    )
                )
                cell_id = None

        report_date = None
        if mapped_data.get("report_date"):
            date_result = coerce_value(mapped_data.get("report_date"), "date")
            if date_result.success:
                report_date = date_result.coerced_value
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="report_date",
                        error_type="coercion",
                        message=date_result.error or "Invalid date",
                        original_value=mapped_data.get("report_date"),
                    )
                )
        else:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="report_date",
                    error_type="required",
                    message="report_date is required",
                    original_value=None,
                )
            )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Validate references
        ref_errors = self.validate_references(
            db, mapped_data, tenant_id, exclude_person_id=None
        )
        if ref_errors:
            errors.extend(ref_errors)
            return ProcessResult(success=False, errors=errors)

        # Coerce values
        from app.common.models.base import MeetingType, CellReportStatus
        from decimal import Decimal

        report_time = None
        if mapped_data.get("report_time"):
            time_result = coerce_value(mapped_data.get("report_time"), "time")
            if time_result.success:
                report_time = time_result.coerced_value

        attendance = 0
        if mapped_data.get("attendance"):
            int_result = coerce_value(mapped_data.get("attendance"), "integer")
            if int_result.success:
                attendance = int_result.coerced_value

        first_timers = 0
        if mapped_data.get("first_timers"):
            int_result = coerce_value(mapped_data.get("first_timers"), "integer")
            if int_result.success:
                first_timers = int_result.coerced_value

        new_converts = 0
        if mapped_data.get("new_converts"):
            int_result = coerce_value(mapped_data.get("new_converts"), "integer")
            if int_result.success:
                new_converts = int_result.coerced_value

        offerings_total = Decimal("0.00")
        if mapped_data.get("offerings_total"):
            decimal_result = coerce_value(
                mapped_data.get("offerings_total"), "decimal"
            )
            if decimal_result.success:
                offerings_total = decimal_result.coerced_value

        meeting_type = "bible_study"
        if mapped_data.get("meeting_type"):
            meeting_type_result = coerce_value(
                mapped_data.get("meeting_type"),
                "enum",
                {"enum_class": MeetingType},
            )
            if meeting_type_result.success:
                meeting_type = meeting_type_result.coerced_value

        status = "submitted"
        if mapped_data.get("status"):
            status_result = coerce_value(
                mapped_data.get("status"),
                "enum",
                {"enum_class": CellReportStatus},
            )
            if status_result.success:
                status = status_result.coerced_value

        testimonies = mapped_data.get("testimonies", "").strip() or None
        notes = mapped_data.get("notes", "").strip() or None

        if errors:
            return ProcessResult(success=False, errors=errors)

        try:
            if not cell_id:
                return ProcessResult(success=False, errors=errors)

            cell_report = CellReportService.create_report(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                report_date=report_date,
                attendance=attendance,
                first_timers=first_timers,
                new_converts=new_converts,
                testimonies=testimonies,
                offerings_total=offerings_total,
                meeting_type=meeting_type,
                report_time=report_time,
                notes=notes,
            )
            return ProcessResult(
                success=True, entity_id=cell_report.id, warnings=warnings
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="",
                    error_type="business",
                    message=str(e),
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for CellReport."""
        errors = []
        if "cell_id" in row and row["cell_id"]:
            valid, error_msg = validate_cell_reference(
                db, str(tenant_id), str(row["cell_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="cell_id",
                        error_type="reference",
                        message=error_msg or "Cell not found",
                        original_value=row["cell_id"],
                    )
                )
        return errors

    def requires_org_unit(self) -> bool:
        """CellReport processor does not require org_unit_id."""
        return False


class FinanceEntryProcessor(EntityProcessor):
    """Processor for FinanceEntry entity."""

    def process_row(
        self,
        db: Session,
        row: dict[str, Any],
        mapping: dict[str, str],
        mode: str,
        tenant_id: UUID,
        user_id: UUID,
        org_unit_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a FinanceEntry row."""
        errors = []
        warnings = []

        # Map row data to FinanceEntry fields
        mapped_data = {}
        for source_col, target_field in mapping.items():
            if source_col in row:
                mapped_data[target_field] = row[source_col]

        # Get required fields
        fund_id_str = mapped_data.get("fund_id")
        if not fund_id_str:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="fund_id",
                    error_type="required",
                    message="fund_id is required",
                    original_value=None,
                )
            )
        else:
            try:
                fund_id = UUID(str(fund_id_str))
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="fund_id",
                        error_type="reference",
                        message="Invalid fund_id format",
                        original_value=fund_id_str,
                    )
                )
                fund_id = None

        amount = None
        if mapped_data.get("amount"):
            decimal_result = coerce_value(mapped_data.get("amount"), "decimal")
            if decimal_result.success:
                amount = decimal_result.coerced_value
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="amount",
                        error_type="coercion",
                        message=decimal_result.error or "Invalid amount",
                        original_value=mapped_data.get("amount"),
                    )
                )
        else:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="amount",
                    error_type="required",
                    message="amount is required",
                    original_value=None,
                )
            )

        transaction_date = None
        if mapped_data.get("transaction_date"):
            date_result = coerce_value(
                mapped_data.get("transaction_date"), "date"
            )
            if date_result.success:
                transaction_date = date_result.coerced_value
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="transaction_date",
                        error_type="coercion",
                        message=date_result.error or "Invalid date",
                        original_value=mapped_data.get("transaction_date"),
                    )
                )
        else:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="transaction_date",
                    error_type="required",
                    message="transaction_date is required",
                    original_value=None,
                )
            )

        # Get org_unit_id (required)
        if not org_unit_id:
            org_unit_id_str = mapped_data.get("org_unit_id")
            if org_unit_id_str:
                try:
                    org_unit_id = UUID(org_unit_id_str)
                except (ValueError, TypeError):
                    errors.append(
                        ValidationError(
                            row_number=row.get("_row_number", 0),
                            field="org_unit_id",
                            error_type="reference",
                            message="Invalid org_unit_id format",
                            original_value=org_unit_id_str,
                        )
                    )
            else:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="org_unit_id",
                        error_type="required",
                        message="org_unit_id is required",
                        original_value=None,
                    )
                )

        if errors:
            return ProcessResult(success=False, errors=errors)

        # Validate references
        ref_errors = self.validate_references(
            db, mapped_data, tenant_id, exclude_person_id=None
        )
        if ref_errors:
            errors.extend(ref_errors)
            return ProcessResult(success=False, errors=errors)

        # Coerce optional values
        from app.common.models.base import PaymentMethod, VerifiedStatus, SourceType

        batch_id = None
        if mapped_data.get("batch_id"):
            try:
                batch_id = UUID(str(mapped_data.get("batch_id")))
            except (ValueError, TypeError):
                pass  # Optional field

        service_id = None
        if mapped_data.get("service_id"):
            try:
                service_id = UUID(str(mapped_data.get("service_id")))
            except (ValueError, TypeError):
                pass  # Optional field

        partnership_arm_id = None
        if mapped_data.get("partnership_arm_id"):
            try:
                partnership_arm_id = UUID(
                    str(mapped_data.get("partnership_arm_id"))
                )
            except (ValueError, TypeError):
                pass  # Optional field

        currency = mapped_data.get("currency", "EUR").strip() or "EUR"
        method = "cash"
        if mapped_data.get("method"):
            method_result = coerce_value(
                mapped_data.get("method"),
                "enum",
                {"enum_class": PaymentMethod},
            )
            if method_result.success:
                method = method_result.coerced_value

        person_id = None
        if mapped_data.get("person_id"):
            try:
                person_id = UUID(str(mapped_data.get("person_id")))
            except (ValueError, TypeError):
                pass  # Optional field

        cell_id = None
        if mapped_data.get("cell_id"):
            try:
                cell_id = UUID(str(mapped_data.get("cell_id")))
            except (ValueError, TypeError):
                pass  # Optional field

        external_giver_name = (
            mapped_data.get("external_giver_name", "").strip() or None
        )
        reference = mapped_data.get("reference", "").strip() or None
        comment = mapped_data.get("comment", "").strip() or None

        verified_status = "draft"
        if mapped_data.get("verified_status"):
            status_result = coerce_value(
                mapped_data.get("verified_status"),
                "enum",
                {"enum_class": VerifiedStatus},
            )
            if status_result.success:
                verified_status = status_result.coerced_value

        source_type = "manual"
        if mapped_data.get("source_type"):
            source_result = coerce_value(
                mapped_data.get("source_type"),
                "enum",
                {"enum_class": SourceType},
            )
            if source_result.success:
                source_type = source_result.coerced_value

        # Business rule: at least one giver must be specified
        if not person_id and not cell_id and not external_giver_name:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="",
                    error_type="business",
                    message=(
                        "At least one of person_id, cell_id, or "
                        "external_giver_name must be provided"
                    ),
                    original_value=None,
                )
            )

        if errors:
            return ProcessResult(success=False, errors=errors)

        try:
            if not fund_id or not amount or not transaction_date or not org_unit_id:
                return ProcessResult(success=False, errors=errors)

            entry = FinanceEntryService.create_entry(
                db=db,
                creator_id=user_id,
                tenant_id=tenant_id,
                org_unit_id=org_unit_id,
                fund_id=fund_id,
                amount=amount,
                transaction_date=transaction_date,
                batch_id=batch_id,
                service_id=service_id,
                partnership_arm_id=partnership_arm_id,
                currency=currency,
                method=method,
                person_id=person_id,
                cell_id=cell_id,
                external_giver_name=external_giver_name,
                reference=reference,
                comment=comment,
                source_type=source_type,
                source_id=None,
            )
            return ProcessResult(success=True, entity_id=entry.id, warnings=warnings)
        except Exception as e:
            errors.append(
                ValidationError(
                    row_number=row.get("_row_number", 0),
                    field="",
                    error_type="business",
                    message=str(e),
                    original_value=None,
                )
            )
            return ProcessResult(success=False, errors=errors)

    def validate_references(
        self,
        db: Session,
        row: dict[str, Any],
        tenant_id: UUID,
        exclude_person_id: Optional[str] = None,
    ) -> list[ValidationError]:
        """Validate references for FinanceEntry."""
        errors = []

        if "fund_id" in row and row["fund_id"]:
            valid, error_msg = validate_fund_reference(
                db, str(tenant_id), str(row["fund_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="fund_id",
                        error_type="reference",
                        message=error_msg or "Fund not found",
                        original_value=row["fund_id"],
                    )
                )

        if "batch_id" in row and row["batch_id"]:
            valid, error_msg = validate_batch_reference(
                db, str(tenant_id), str(row["batch_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="batch_id",
                        error_type="reference",
                        message=error_msg or "Batch not found or locked",
                        original_value=row["batch_id"],
                    )
                )

        if "service_id" in row and row["service_id"]:
            valid, error_msg = validate_service_reference(
                db, str(tenant_id), str(row["service_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="service_id",
                        error_type="reference",
                        message=error_msg or "Service not found",
                        original_value=row["service_id"],
                    )
                )

        if "partnership_arm_id" in row and row["partnership_arm_id"]:
            valid, error_msg = validate_partnership_arm_reference(
                db, str(tenant_id), str(row["partnership_arm_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="partnership_arm_id",
                        error_type="reference",
                        message=error_msg or "Partnership arm not found",
                        original_value=row["partnership_arm_id"],
                    )
                )

        if "cell_id" in row and row["cell_id"]:
            valid, error_msg = validate_cell_reference(
                db, str(tenant_id), str(row["cell_id"])
            )
            if not valid:
                errors.append(
                    ValidationError(
                        row_number=row.get("_row_number", 0),
                        field="cell_id",
                        error_type="reference",
                        message=error_msg or "Cell not found",
                        original_value=row["cell_id"],
                    )
                )

        return errors


# Processor registry
PROCESSORS = {
    "people": PeopleProcessor(),
    "memberships": MembershipProcessor(),
    "first_timers": FirstTimerProcessor(),
    "services": ServiceProcessor(),
    "attendance": AttendanceProcessor(),
    "cells": CellProcessor(),
    "cell_reports": CellReportProcessor(),
    "finance_entries": FinanceEntryProcessor(),
}


def get_processor(entity_type: str) -> EntityProcessor:
    """Get processor for entity type."""
    return PROCESSORS.get(entity_type, PeopleProcessor())  # Default to People

