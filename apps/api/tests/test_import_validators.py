"""Tests for import validators."""

from __future__ import annotations

from datetime import date

import pytest

from app.imports.validators import (
    validate_required,
    validate_email_format,
    validate_phone_format,
    validate_date_range,
    validate_string_length,
    validate_org_unit_reference,
    validate_service_reference,
    validate_cell_reference,
    validate_fund_reference,
    validate_batch_reference,
    validate_partnership_arm_reference,
    validate_unique_email,
    validate_unique_member_code,
    validate_business_rules,
    ValidationError,
)


class TestRequiredValidation:
    """Tests for required field validation."""

    def test_validate_required_present(self):
        """Test validating required field that is present."""
        assert validate_required("value", "field_name") is None

    def test_validate_required_missing(self):
        """Test validating required field that is missing."""
        error = validate_required(None, "field_name")
        assert error is not None
        assert "required" in error.lower()

    def test_validate_required_empty_string(self):
        """Test validating required field that is empty string."""
        error = validate_required("", "field_name")
        assert error is not None


class TestFormatValidation:
    """Tests for format validation."""

    def test_validate_email_format_valid(self):
        """Test validating valid email."""
        assert validate_email_format("test@example.com") is None

    def test_validate_email_format_invalid(self):
        """Test validating invalid email."""
        error = validate_email_format("not-an-email")
        assert error is not None

    def test_validate_phone_format_valid(self):
        """Test validating valid phone."""
        assert validate_phone_format("+3531234567890") is None

    def test_validate_phone_format_too_short(self):
        """Test validating phone that is too short."""
        error = validate_phone_format("123")
        assert error is not None


class TestDateValidation:
    """Tests for date validation."""

    def test_validate_date_range_valid(self):
        """Test validating date within range."""
        test_date = date(2024, 1, 15)
        min_date = date(2024, 1, 1)
        max_date = date(2024, 12, 31)
        assert validate_date_range(test_date, min_date, max_date) is None

    def test_validate_date_range_before_min(self):
        """Test validating date before minimum."""
        test_date = date(2023, 12, 31)
        min_date = date(2024, 1, 1)
        error = validate_date_range(test_date, min_date, None)
        assert error is not None

    def test_validate_date_range_after_max(self):
        """Test validating date after maximum."""
        test_date = date(2025, 1, 1)
        max_date = date(2024, 12, 31)
        error = validate_date_range(test_date, None, max_date)
        assert error is not None


class TestStringValidation:
    """Tests for string validation."""

    def test_validate_string_length_valid(self):
        """Test validating string within length limit."""
        assert validate_string_length("short", 100) is None

    def test_validate_string_length_too_long(self):
        """Test validating string that is too long."""
        long_string = "a" * 101
        error = validate_string_length(long_string, 100)
        assert error is not None


class TestReferenceValidation:
    """Tests for reference validation."""

    def test_validate_org_unit_reference_exists(self, db, tenant_id, test_org_unit):
        """Test validating org unit that exists."""
        valid, error = validate_org_unit_reference(
            db, tenant_id, str(test_org_unit.id)
        )
        assert valid
        assert error is None

    def test_validate_org_unit_reference_not_exists(self, db, tenant_id):
        """Test validating org unit that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_org_unit_reference(db, tenant_id, str(uuid4()))
        assert not valid
        assert error is not None

    def test_validate_org_unit_reference_invalid_format(self, db, tenant_id):
        """Test validating org unit with invalid UUID format."""
        valid, error = validate_org_unit_reference(db, tenant_id, "not-a-uuid")
        assert not valid
        assert "Invalid" in error or "format" in error.lower()

    def test_validate_service_reference_exists(self, db, tenant_id):
        """Test validating service that exists."""
        from uuid import uuid4, UUID
        from app.common.models import Service, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a test service
        from datetime import date
        service = Service(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            name="Sunday",
            service_date=date.today(),
        )
        db.add(service)
        db.commit()

        valid, error = validate_service_reference(
            db, str(tenant_id), str(service.id)
        )
        assert valid
        assert error is None

    def test_validate_service_reference_not_exists(self, db, tenant_id):
        """Test validating service that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_service_reference(db, str(tenant_id), str(uuid4()))
        assert not valid
        assert error is not None

    def test_validate_cell_reference_exists(self, db, tenant_id):
        """Test validating cell that exists."""
        from uuid import uuid4, UUID
        from app.common.models import Cell, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a test cell
        cell = Cell(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            name="Test Cell",
        )
        db.add(cell)
        db.commit()

        valid, error = validate_cell_reference(db, str(tenant_id), str(cell.id))
        assert valid
        assert error is None

    def test_validate_cell_reference_not_exists(self, db, tenant_id):
        """Test validating cell that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_cell_reference(db, str(tenant_id), str(uuid4()))
        assert not valid
        assert error is not None

    def test_validate_fund_reference_exists(self, db, tenant_id):
        """Test validating fund that exists."""
        from uuid import uuid4, UUID
        from app.common.models import Fund

        fund = Fund(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Fund",
            is_partnership=False,
            active=True,
        )
        db.add(fund)
        db.commit()

        valid, error = validate_fund_reference(db, str(tenant_id), str(fund.id))
        assert valid
        assert error is None

    def test_validate_fund_reference_not_exists(self, db, tenant_id):
        """Test validating fund that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_fund_reference(db, str(tenant_id), str(uuid4()))
        assert not valid
        assert error is not None

    def test_validate_batch_reference_exists(self, db, tenant_id):
        """Test validating batch that exists."""
        from uuid import uuid4, UUID
        from app.common.models import Batch, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        batch = Batch(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            status="draft",
        )
        db.add(batch)
        db.commit()

        valid, error = validate_batch_reference(db, str(tenant_id), str(batch.id))
        assert valid
        assert error is None

    def test_validate_batch_reference_locked(self, db, tenant_id):
        """Test validating locked batch."""
        from uuid import uuid4, UUID
        from app.common.models import Batch, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        batch = Batch(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            status="locked",
        )
        db.add(batch)
        db.commit()

        valid, error = validate_batch_reference(db, str(tenant_id), str(batch.id))
        assert not valid
        assert "locked" in error.lower()

    def test_validate_batch_reference_not_exists(self, db, tenant_id):
        """Test validating batch that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_batch_reference(db, str(tenant_id), str(uuid4()))
        assert not valid
        assert error is not None

    def test_validate_partnership_arm_reference_exists(self, db, tenant_id):
        """Test validating partnership arm that exists."""
        from uuid import uuid4, UUID
        from datetime import date
        from app.common.models import PartnershipArm

        arm = PartnershipArm(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Partnership Arm",
            active_from=date.today(),
            active=True,
        )
        db.add(arm)
        db.commit()

        valid, error = validate_partnership_arm_reference(
            db, str(tenant_id), str(arm.id)
        )
        assert valid
        assert error is None

    def test_validate_partnership_arm_reference_not_exists(self, db, tenant_id):
        """Test validating partnership arm that doesn't exist."""
        from uuid import uuid4

        valid, error = validate_partnership_arm_reference(
            db, str(tenant_id), str(uuid4())
        )
        assert not valid
        assert error is not None


class TestBusinessRulesValidation:
    """Tests for business rules validation."""

    def test_validate_business_rules_join_date_future(self):
        """Test validating join date in future."""
        from datetime import date, timedelta

        future_date = date.today() + timedelta(days=1)
        row_data = {"join_date": future_date, "_row_number": 1}
        errors = validate_business_rules("people", row_data)
        assert len(errors) > 0
        assert any("future" in e.message.lower() for e in errors)

    def test_validate_business_rules_dob_future(self):
        """Test validating date of birth in future."""
        from datetime import date, timedelta

        future_date = date.today() + timedelta(days=1)
        row_data = {"dob": future_date, "_row_number": 1}
        errors = validate_business_rules("people", row_data)
        assert len(errors) > 0
        assert any("future" in e.message.lower() for e in errors)

    def test_validate_business_rules_valid_dates(self):
        """Test validating valid dates."""
        from datetime import date, timedelta

        past_date = date.today() - timedelta(days=365)
        row_data = {"join_date": past_date, "dob": past_date, "_row_number": 1}
        errors = validate_business_rules("people", row_data)
        assert len(errors) == 0


class TestUniqueValidation:
    """Tests for unique field validation."""

    def test_validate_unique_email_new(self, db, tenant_id):
        """Test validating unique email that doesn't exist."""
        valid, error = validate_unique_email(db, str(tenant_id), "new@example.com")
        assert valid
        assert error is None

    def test_validate_unique_email_exists(self, db, tenant_id):
        """Test validating unique email that already exists."""
        from uuid import uuid4, UUID
        from app.common.models import People, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a person with email
        person = People(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            first_name="Test",
            last_name="User",
            gender="male",
            email="existing@example.com",
        )
        db.add(person)
        db.commit()

        valid, error = validate_unique_email(
            db, str(tenant_id), "existing@example.com"
        )
        assert not valid
        assert "already exists" in error.lower()

    def test_validate_unique_email_with_exclude(self, db, tenant_id):
        """Test validating unique email with exclude_person_id."""
        from uuid import uuid4, UUID
        from app.common.models import People, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a person with email
        person = People(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            first_name="Test",
            last_name="User",
            gender="male",
            email="test@example.com",
        )
        db.add(person)
        db.commit()

        # Should be valid when excluding the same person
        valid, error = validate_unique_email(
            db, str(tenant_id), "test@example.com", exclude_person_id=str(person.id)
        )
        assert valid
        assert error is None

    def test_validate_unique_email_empty(self, db, tenant_id):
        """Test validating empty email (optional field)."""
        valid, error = validate_unique_email(db, str(tenant_id), "")
        assert valid
        assert error is None

    def test_validate_unique_member_code_new(self, db, tenant_id):
        """Test validating unique member code that doesn't exist."""
        valid, error = validate_unique_member_code(
            db, str(tenant_id), "NEW123"
        )
        assert valid
        assert error is None

    def test_validate_unique_member_code_exists(self, db, tenant_id):
        """Test validating unique member code that already exists."""
        from uuid import uuid4, UUID
        from app.common.models import People, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a person with member_code
        person = People(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            first_name="Test",
            last_name="User",
            gender="male",
            member_code="EXIST123",
        )
        db.add(person)
        db.commit()

        valid, error = validate_unique_member_code(
            db, str(tenant_id), "EXIST123"
        )
        assert not valid
        assert "already exists" in error.lower()

    def test_validate_unique_member_code_with_exclude(self, db, tenant_id):
        """Test validating unique member code with exclude_person_id."""
        from uuid import uuid4, UUID
        from app.common.models import People, OrgUnit

        # Create a test org unit first
        org_unit = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Org",
            type="church",
        )
        db.add(org_unit)
        db.flush()

        # Create a person with member_code
        person = People(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=org_unit.id,
            first_name="Test",
            last_name="User",
            gender="male",
            member_code="TEST123",
        )
        db.add(person)
        db.commit()

        # Should be valid when excluding the same person
        valid, error = validate_unique_member_code(
            db, str(tenant_id), "TEST123", exclude_person_id=str(person.id)
        )
        assert valid
        assert error is None

    def test_validate_unique_member_code_empty(self, db, tenant_id):
        """Test validating empty member code (optional field)."""
        valid, error = validate_unique_member_code(db, str(tenant_id), "")
        assert valid
        assert error is None

