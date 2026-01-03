"""Data type coercion for import values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
import phonenumbers
from dateutil import parser as date_parser

from app.common.models.base import (
    Gender,
    MaritalStatus,
    MembershipStatus,
    FirstTimerStatus,
    MeetingDay,
)


@dataclass
class CoercionResult:
    """Result of coercion operation."""

    success: bool
    coerced_value: Any = None
    warnings: list[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.warnings is None:
            self.warnings = []


# Date format patterns
DATE_PATTERNS = [
    "%Y-%m-%d",  # ISO format
    "%d/%m/%Y",  # DD/MM/YYYY
    "%m/%d/%Y",  # MM/DD/YYYY
    "%d-%m-%Y",  # DD-MM-YYYY
    "%Y/%m/%d",  # YYYY/MM/DD
    "%d.%m.%Y",  # DD.MM.YYYY
    "%d %B %Y",  # DD Month YYYY
    "%B %d, %Y",  # Month DD, YYYY
]

# Boolean patterns
BOOLEAN_TRUE = ["true", "yes", "1", "y", "on", "enabled", "active"]
BOOLEAN_FALSE = ["false", "no", "0", "n", "off", "disabled", "inactive"]


def coerce_date(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to date."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    # Convert to string if not already
    str_value = str(value).strip()

    # Try dateutil parser first (most flexible)
    try:
        parsed = date_parser.parse(str_value, dayfirst=True, yearfirst=False)
        if isinstance(parsed, datetime):
            return CoercionResult(success=True, coerced_value=parsed.date())
        elif isinstance(parsed, date):
            return CoercionResult(success=True, coerced_value=parsed)
    except (ValueError, TypeError):
        pass

    # Try specific patterns
    for pattern in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(str_value, pattern)
            return CoercionResult(success=True, coerced_value=parsed.date())
        except (ValueError, TypeError):
            continue

    return CoercionResult(
        success=False,
        error=f"Could not parse date: {str_value}",
    )


def coerce_datetime(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to datetime."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()

    # Try dateutil parser
    try:
        parsed = date_parser.parse(str_value, dayfirst=True, yearfirst=False)
        return CoercionResult(success=True, coerced_value=parsed)
    except (ValueError, TypeError):
        pass

    return CoercionResult(
        success=False,
        error=f"Could not parse datetime: {str_value}",
    )


def coerce_time(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to time."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()

    # Try time patterns
    time_patterns = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]
    for pattern in time_patterns:
        try:
            parsed = datetime.strptime(str_value, pattern).time()
            return CoercionResult(success=True, coerced_value=parsed)
        except (ValueError, TypeError):
            continue

    return CoercionResult(
        success=False,
        error=f"Could not parse time: {str_value}",
    )


def coerce_boolean(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to boolean."""
    if value is None or value == "":
        return CoercionResult(success=True, coerced_value=False)

    str_value = str(value).strip().lower()

    if str_value in BOOLEAN_TRUE:
        return CoercionResult(success=True, coerced_value=True)
    elif str_value in BOOLEAN_FALSE:
        return CoercionResult(success=True, coerced_value=False)

    # Try numeric
    try:
        num = float(str_value)
        return CoercionResult(success=True, coerced_value=bool(num))
    except (ValueError, TypeError):
        pass

    return CoercionResult(
        success=False,
        error=f"Could not parse boolean: {str_value}",
    )


def coerce_integer(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to integer."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()

    # Remove common formatting
    str_value = str_value.replace(",", "").replace(" ", "")

    try:
        return CoercionResult(success=True, coerced_value=int(float(str_value)))
    except (ValueError, TypeError):
        return CoercionResult(
            success=False,
            error=f"Could not parse integer: {str_value}",
        )


def coerce_decimal(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to Decimal."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()

    # Remove common currency symbols and formatting
    # Remove common currency symbols (€, $, £, ¥, etc.)
    currency_symbols = [
        "€", "$", "£", "¥", "₹", "₽", "₦", "₨", "₩", "₪", "₫", "₭",
        "₮", "₯", "₰", "₱", "₲", "₳", "₴", "₵", "₶", "₷", "₸", "₹",
        "₺", "₻", "₼", "₽", "₾", "₿",
    ]
    for symbol in currency_symbols:
        str_value = str_value.replace(symbol, "")
    str_value = str_value.replace(",", "").replace(" ", "")

    try:
        return CoercionResult(success=True, coerced_value=Decimal(str_value))
    except (InvalidOperation, ValueError, TypeError):
        return CoercionResult(
            success=False,
            error=f"Could not parse decimal: {str_value}",
        )


def coerce_email(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce and validate email."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip().lower()

    # Basic email validation
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, str_value):
        return CoercionResult(
            success=False,
            error=f"Invalid email format: {str_value}",
        )

    return CoercionResult(success=True, coerced_value=str_value)


def coerce_phone(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce and normalize phone number."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()

    # Remove common formatting
    cleaned = re.sub(r"[^\d+]", "", str_value)

    # Try to parse with phonenumbers (default to Ireland/IE)
    try:
        parsed = phonenumbers.parse(cleaned, "IE")
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
            return CoercionResult(success=True, coerced_value=formatted)
        else:
            # Still return the cleaned number with a warning
            return CoercionResult(
                success=True,
                coerced_value=cleaned,
                warnings=["Phone number may be invalid"],
            )
    except (phonenumbers.NumberParseException, Exception):
        # Fallback to cleaned number
        return CoercionResult(
            success=True,
            coerced_value=cleaned,
            warnings=["Could not fully validate phone number"],
        )


def coerce_enum(value: Any, enum_class: type, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to enum."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip().lower()

    # Fuzzy matching for common variations
    gender_mappings = {
        "m": "male",
        "male": "male",
        "f": "female",
        "female": "female",
        "o": "other",
        "other": "other",
    }

    marital_mappings = {
        "s": "single",
        "single": "single",
        "m": "married",
        "married": "married",
        "d": "divorced",
        "divorced": "divorced",
        "w": "widowed",
        "widowed": "widowed",
        "sep": "separated",
        "separated": "separated",
    }

    membership_mappings = {
        "visitor": "visitor",
        "regular": "regular",
        "member": "member",
        "partner": "partner",
    }

    first_timer_mappings = {
        "new": "New",
        "contacted": "Contacted",
        "returned": "Returned",
        "member": "Member",
    }

    meeting_day_mappings = {
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday",
        "saturday": "Saturday",
        "sunday": "Sunday",
        "mon": "Monday",
        "tue": "Tuesday",
        "wed": "Wednesday",
        "thu": "Thursday",
        "fri": "Friday",
        "sat": "Saturday",
        "sun": "Sunday",
    }

    # Use specific mappings if available
    # Compare by name attribute for SQLAlchemy Enum types
    enum_name = getattr(enum_class, "name", None)
    
    if enum_name == "gender" or enum_class is Gender:
        if str_value in gender_mappings:
            return CoercionResult(
                success=True, coerced_value=gender_mappings[str_value]
            )
        enum_values = ["male", "female", "other"]
    elif enum_name == "marital_status" or enum_class is MaritalStatus:
        if str_value in marital_mappings:
            return CoercionResult(
                success=True, coerced_value=marital_mappings[str_value]
            )
        enum_values = ["single", "married", "divorced", "widowed", "separated"]
    elif enum_name == "membership_status" or enum_class is MembershipStatus:
        if str_value in membership_mappings:
            return CoercionResult(
                success=True, coerced_value=membership_mappings[str_value]
            )
        enum_values = ["visitor", "regular", "member", "partner"]
    elif enum_name == "first_timer_status" or enum_class is FirstTimerStatus:
        if str_value in first_timer_mappings:
            return CoercionResult(
                success=True, coerced_value=first_timer_mappings[str_value]
            )
        enum_values = ["New", "Contacted", "Returned", "Member"]
    elif enum_name == "meeting_day" or enum_class is MeetingDay:
        if str_value in meeting_day_mappings:
            return CoercionResult(
                success=True, coerced_value=meeting_day_mappings[str_value]
            )
        enum_values = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
    else:
        # Try to extract enum values from SQLAlchemy Enum type
        enum_values = []
        try:
            # SQLAlchemy Enum types may have enums attribute
            if hasattr(enum_class, "enums"):
                enum_values = [str(e).lower() for e in enum_class.enums]
            # Or try to get from python_type
            elif hasattr(enum_class, "python_type"):
                python_enum = enum_class.python_type
                if hasattr(python_enum, "__members__"):
                    enum_values = [
                        v.value.lower()
                        for v in python_enum.__members__.values()
                    ]
        except (AttributeError, TypeError):
            pass

    # Try direct match with enum values (case-insensitive)
    enum_values_lower = [v.lower() for v in enum_values]
    if str_value in enum_values_lower:
        # Find the actual enum value (preserving original case)
        for ev in enum_values:
            if ev.lower() == str_value:
                return CoercionResult(success=True, coerced_value=ev)

    return CoercionResult(
        success=False,
        error=f"Invalid enum value: {str_value}. Valid values: {', '.join(enum_values) if enum_values else 'unknown'}",
    )


def coerce_string(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Coerce value to string."""
    if value is None:
        return CoercionResult(success=True, coerced_value="")

    str_value = str(value).strip()
    # Apply max length if specified
    max_length = hints.get("max_length") if hints else None
    if max_length and len(str_value) > max_length:
        return CoercionResult(
            success=False,
            error=f"String too long: {len(str_value)} > {max_length}",
        )

    return CoercionResult(success=True, coerced_value=str_value)


def coerce_name_split(value: Any, hints: Optional[dict] = None) -> CoercionResult:
    """Split full name into first and last name."""
    if value is None or value == "":
        return CoercionResult(success=False, error="Empty value")

    str_value = str(value).strip()
    parts = str_value.split()

    if len(parts) == 0:
        return CoercionResult(success=False, error="No name parts found")
    elif len(parts) == 1:
        # Single name - assume first name
        return CoercionResult(
            success=True,
            coerced_value={"first_name": parts[0], "last_name": ""},
        )
    else:
        # Multiple parts - first is first name, rest is last name
        return CoercionResult(
            success=True,
            coerced_value={
                "first_name": parts[0],
                "last_name": " ".join(parts[1:]),
            },
        )


# Type coercion registry
COERCION_FUNCTIONS = {
    "date": coerce_date,
    "datetime": coerce_datetime,
    "time": coerce_time,
    "boolean": coerce_boolean,
    "integer": coerce_integer,
    "decimal": coerce_decimal,
    "email": coerce_email,
    "phone": coerce_phone,
    "string": coerce_string,
    "name_split": coerce_name_split,
}


def coerce_value(
    value: Any, target_type: str, hints: Optional[dict] = None
) -> CoercionResult:
    """
    Coerce value to target type.

    Args:
        value: Value to coerce
        target_type: Target type name (e.g., "date", "integer", "email", "enum")
        hints: Additional hints for coercion (e.g., {"max_length": 100, "enum_class": Gender})

    Returns:
        CoercionResult with success status and coerced value
    """
    # Handle enum type specially (requires enum_class in hints)
    if target_type == "enum":
        if hints and "enum_class" in hints:
            return coerce_enum(value, hints["enum_class"], hints)
        else:
            return CoercionResult(
                success=False,
                error="enum_class must be provided in hints for enum coercion",
            )

    if target_type not in COERCION_FUNCTIONS:
        # Default to string
        return coerce_string(value, hints)

    coercion_func = COERCION_FUNCTIONS[target_type]
    return coercion_func(value, hints)

