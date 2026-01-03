"""Tests for import data coercion."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.imports.coercers import (
    coerce_value,
    coerce_date,
    coerce_datetime,
    coerce_time,
    coerce_email,
    coerce_phone,
    coerce_boolean,
    coerce_integer,
    coerce_decimal,
    coerce_enum,
    coerce_string,
    coerce_name_split,
    CoercionResult,
)
from app.common.models import (
    Gender,
    MaritalStatus,
    MembershipStatus,
    FirstTimerStatus,
    MeetingDay,
)


class TestDateCoercion:
    """Tests for date coercion."""

    def test_coerce_date_iso_format(self):
        """Test coercing ISO date format."""
        result = coerce_date("2024-01-15")
        assert result.success
        assert result.coerced_value == date(2024, 1, 15)

    def test_coerce_date_dd_mm_yyyy(self):
        """Test coercing DD/MM/YYYY format."""
        result = coerce_date("15/01/2024")
        assert result.success
        assert result.coerced_value == date(2024, 1, 15)

    def test_coerce_date_invalid(self):
        """Test coercing invalid date."""
        result = coerce_date("invalid-date")
        assert not result.success
        assert result.error is not None

    def test_coerce_date_empty(self):
        """Test coercing empty date."""
        result = coerce_date("")
        assert not result.success
        assert result.error is not None

    def test_coerce_date_none(self):
        """Test coercing None date."""
        result = coerce_date(None)
        assert not result.success
        assert result.error is not None


class TestDateTimeCoercion:
    """Tests for datetime coercion."""

    def test_coerce_datetime_iso_format(self):
        """Test coercing ISO datetime format."""
        result = coerce_datetime("2024-01-15T10:30:00")
        assert result.success
        assert isinstance(result.coerced_value, datetime)

    def test_coerce_datetime_with_timezone(self):
        """Test coercing datetime with timezone."""
        result = coerce_datetime("2024-01-15T10:30:00+00:00")
        assert result.success
        assert isinstance(result.coerced_value, datetime)

    def test_coerce_datetime_invalid(self):
        """Test coercing invalid datetime."""
        result = coerce_datetime("invalid-datetime")
        assert not result.success
        assert result.error is not None

    def test_coerce_datetime_empty(self):
        """Test coercing empty datetime."""
        result = coerce_datetime("")
        assert not result.success
        assert result.error is not None

    def test_coerce_datetime_none(self):
        """Test coercing None datetime."""
        result = coerce_datetime(None)
        assert not result.success
        assert result.error is not None


class TestTimeCoercion:
    """Tests for time coercion."""

    def test_coerce_time_hh_mm_ss(self):
        """Test coercing time in HH:MM:SS format."""
        result = coerce_time("10:30:00")
        assert result.success
        assert isinstance(result.coerced_value, time)

    def test_coerce_time_hh_mm(self):
        """Test coercing time in HH:MM format."""
        result = coerce_time("10:30")
        assert result.success
        assert isinstance(result.coerced_value, time)

    def test_coerce_time_12_hour(self):
        """Test coercing time in 12-hour format."""
        result = coerce_time("10:30 AM")
        assert result.success
        assert isinstance(result.coerced_value, time)

    def test_coerce_time_invalid(self):
        """Test coercing invalid time."""
        result = coerce_time("invalid-time")
        assert not result.success
        assert result.error is not None

    def test_coerce_time_empty(self):
        """Test coercing empty time."""
        result = coerce_time("")
        assert not result.success
        assert result.error is not None

    def test_coerce_time_none(self):
        """Test coercing None time."""
        result = coerce_time(None)
        assert not result.success
        assert result.error is not None


class TestEmailCoercion:
    """Tests for email coercion."""

    def test_coerce_email_valid(self):
        """Test coercing valid email."""
        result = coerce_email("John.Doe@Example.com")
        assert result.success
        assert result.coerced_value == "john.doe@example.com"  # Lowercased

    def test_coerce_email_invalid(self):
        """Test coercing invalid email."""
        result = coerce_email("not-an-email")
        assert not result.success

    def test_coerce_email_empty(self):
        """Test coercing empty email."""
        result = coerce_email("")
        assert not result.success


class TestPhoneCoercion:
    """Tests for phone coercion."""

    def test_coerce_phone_valid(self):
        """Test coercing valid phone."""
        result = coerce_phone("+353 1 234 5678")
        assert result.success
        # Phone should be normalized

    def test_coerce_phone_with_spaces(self):
        """Test coercing phone with spaces."""
        result = coerce_phone("085 123 4567")
        assert result.success


class TestBooleanCoercion:
    """Tests for boolean coercion."""

    def test_coerce_boolean_true(self):
        """Test coercing true values."""
        for value in ["true", "True", "yes", "Yes", "1", "y", "on"]:
            result = coerce_boolean(value)
            assert result.success
            assert result.coerced_value is True

    def test_coerce_boolean_false(self):
        """Test coercing false values."""
        for value in ["false", "False", "no", "No", "0", "n", "off"]:
            result = coerce_boolean(value)
            assert result.success
            assert result.coerced_value is False

    def test_coerce_boolean_empty(self):
        """Test coercing empty boolean."""
        result = coerce_boolean("")
        assert result.success
        assert result.coerced_value is False


class TestIntegerCoercion:
    """Tests for integer coercion."""

    def test_coerce_integer_valid(self):
        """Test coercing valid integer."""
        result = coerce_integer("123")
        assert result.success
        assert result.coerced_value == 123

    def test_coerce_integer_with_commas(self):
        """Test coercing integer with commas."""
        result = coerce_integer("1,234")
        assert result.success
        assert result.coerced_value == 1234

    def test_coerce_integer_invalid(self):
        """Test coercing invalid integer."""
        result = coerce_integer("not-a-number")
        assert not result.success

    def test_coerce_integer_empty(self):
        """Test coercing empty integer."""
        result = coerce_integer("")
        assert not result.success
        assert result.error is not None

    def test_coerce_integer_none(self):
        """Test coercing None integer."""
        result = coerce_integer(None)
        assert not result.success
        assert result.error is not None


class TestDecimalCoercion:
    """Tests for decimal coercion."""

    def test_coerce_decimal_valid(self):
        """Test coercing valid decimal."""
        result = coerce_decimal("123.45")
        assert result.success
        assert result.coerced_value == Decimal("123.45")

    def test_coerce_decimal_with_currency(self):
        """Test coercing decimal with currency symbol."""
        result = coerce_decimal("€123.45")
        assert result.success
        assert result.coerced_value == Decimal("123.45")

    def test_coerce_decimal_with_commas(self):
        """Test coercing decimal with commas."""
        result = coerce_decimal("1,234.56")
        assert result.success
        assert result.coerced_value == Decimal("1234.56")

    def test_coerce_decimal_empty(self):
        """Test coercing empty decimal."""
        result = coerce_decimal("")
        assert not result.success
        assert result.error is not None

    def test_coerce_decimal_none(self):
        """Test coercing None decimal."""
        result = coerce_decimal(None)
        assert not result.success
        assert result.error is not None

    def test_coerce_decimal_invalid(self):
        """Test coercing invalid decimal."""
        result = coerce_decimal("not-a-number")
        assert not result.success
        assert result.error is not None


class TestEnumCoercion:
    """Tests for enum coercion."""

    def test_coerce_enum_gender_male(self):
        """Test coercing gender enum."""
        result = coerce_enum("male", Gender)
        assert result.success
        assert result.coerced_value == "male"

        result = coerce_enum("M", Gender)
        assert result.success
        assert result.coerced_value == "male"

    def test_coerce_enum_marital_status(self):
        """Test coercing marital status enum."""
        result = coerce_enum("married", MaritalStatus)
        assert result.success
        assert result.coerced_value == "married"

        result = coerce_enum("m", MaritalStatus)
        assert result.success
        assert result.coerced_value == "married"

    def test_coerce_enum_invalid(self):
        """Test coercing invalid enum value."""
        result = coerce_enum("invalid", Gender)
        assert not result.success

    def test_coerce_enum_membership_status(self):
        """Test coercing membership status enum."""
        result = coerce_enum("visitor", MembershipStatus)
        assert result.success
        assert result.coerced_value == "visitor"

        result = coerce_enum("regular", MembershipStatus)
        assert result.success
        assert result.coerced_value == "regular"

    def test_coerce_enum_first_timer_status(self):
        """Test coercing first timer status enum."""
        result = coerce_enum("new", FirstTimerStatus)
        assert result.success
        assert result.coerced_value == "New"

        result = coerce_enum("contacted", FirstTimerStatus)
        assert result.success
        assert result.coerced_value == "Contacted"

    def test_coerce_enum_meeting_day(self):
        """Test coercing meeting day enum."""
        result = coerce_enum("monday", MeetingDay)
        assert result.success
        assert result.coerced_value == "Monday"

        result = coerce_enum("mon", MeetingDay)
        assert result.success
        assert result.coerced_value == "Monday"

    def test_coerce_enum_empty(self):
        """Test coercing empty enum value."""
        result = coerce_enum("", Gender)
        assert not result.success
        assert result.error is not None

    def test_coerce_enum_none(self):
        """Test coercing None enum value."""
        result = coerce_enum(None, Gender)
        assert not result.success
        assert result.error is not None


class TestCoerceValue:
    """Tests for generic coerce_value function."""

    def test_coerce_value_date(self):
        """Test coerce_value with date type."""
        result = coerce_value("2024-01-15", "date")
        assert result.success
        assert isinstance(result.coerced_value, date)

    def test_coerce_value_email(self):
        """Test coerce_value with email type."""
        result = coerce_value("Test@Example.com", "email")
        assert result.success
        assert result.coerced_value == "test@example.com"

    def test_coerce_value_enum(self):
        """Test coerce_value with enum type."""
        result = coerce_value("male", "enum", {"enum_class": Gender})
        assert result.success
        assert result.coerced_value == "male"

    def test_coerce_value_enum_missing_hint(self):
        """Test coerce_value with enum type but missing enum_class."""
        result = coerce_value("male", "enum", {})
        assert not result.success
        assert "enum_class" in result.error

    def test_coerce_value_datetime(self):
        """Test coerce_value with datetime type."""
        result = coerce_value("2024-01-15T10:30:00", "datetime")
        assert result.success
        assert isinstance(result.coerced_value, datetime)

    def test_coerce_value_time(self):
        """Test coerce_value with time type."""
        result = coerce_value("10:30:00", "time")
        assert result.success
        assert isinstance(result.coerced_value, time)

    def test_coerce_value_string(self):
        """Test coerce_value with string type."""
        result = coerce_value("test", "string")
        assert result.success
        assert result.coerced_value == "test"

    def test_coerce_value_string_with_max_length(self):
        """Test coerce_value with string type and max_length hint."""
        long_string = "a" * 101
        result = coerce_value(long_string, "string", {"max_length": 100})
        assert not result.success
        assert "too long" in result.error.lower()

    def test_coerce_value_string_none(self):
        """Test coerce_value with string type and None value."""
        result = coerce_value(None, "string")
        assert result.success
        assert result.coerced_value == ""

    def test_coerce_value_name_split(self):
        """Test coerce_value with name_split type."""
        result = coerce_value("John Doe", "name_split")
        assert result.success
        assert result.coerced_value["first_name"] == "John"
        assert result.coerced_value["last_name"] == "Doe"

    def test_coerce_value_unknown_type(self):
        """Test coerce_value with unknown type defaults to string."""
        result = coerce_value("test", "unknown_type")
        assert result.success
        assert result.coerced_value == "test"


class TestNameSplitCoercion:
    """Tests for name split coercion."""

    def test_coerce_name_split_full_name(self):
        """Test splitting full name into first and last."""
        result = coerce_name_split("John Doe")
        assert result.success
        assert result.coerced_value["first_name"] == "John"
        assert result.coerced_value["last_name"] == "Doe"

    def test_coerce_name_split_three_parts(self):
        """Test splitting name with three parts."""
        result = coerce_name_split("John Michael Doe")
        assert result.success
        assert result.coerced_value["first_name"] == "John"
        assert result.coerced_value["last_name"] == "Michael Doe"

    def test_coerce_name_split_single_name(self):
        """Test splitting single name."""
        result = coerce_name_split("John")
        assert result.success
        assert result.coerced_value["first_name"] == "John"
        assert result.coerced_value["last_name"] == ""

    def test_coerce_name_split_empty(self):
        """Test splitting empty name."""
        result = coerce_name_split("")
        assert not result.success
        assert result.error is not None

    def test_coerce_name_split_none(self):
        """Test splitting None name."""
        result = coerce_name_split(None)
        assert not result.success
        assert result.error is not None

    def test_coerce_name_split_whitespace_only(self):
        """Test splitting whitespace-only name."""
        result = coerce_name_split("   ")
        assert not result.success
        assert "No name parts" in result.error


class TestStringCoercion:
    """Tests for string coercion."""

    def test_coerce_string_valid(self):
        """Test coercing valid string."""
        result = coerce_string("test")
        assert result.success
        assert result.coerced_value == "test"

    def test_coerce_string_with_whitespace(self):
        """Test coercing string with whitespace."""
        result = coerce_string("  test  ")
        assert result.success
        assert result.coerced_value == "test"

    def test_coerce_string_none(self):
        """Test coercing None to empty string."""
        result = coerce_string(None)
        assert result.success
        assert result.coerced_value == ""

    def test_coerce_string_with_max_length_valid(self):
        """Test coercing string within max_length."""
        result = coerce_string("test", {"max_length": 10})
        assert result.success
        assert result.coerced_value == "test"

    def test_coerce_string_with_max_length_exceeded(self):
        """Test coercing string exceeding max_length."""
        long_string = "a" * 101
        result = coerce_string(long_string, {"max_length": 100})
        assert not result.success
        assert "too long" in result.error.lower()

