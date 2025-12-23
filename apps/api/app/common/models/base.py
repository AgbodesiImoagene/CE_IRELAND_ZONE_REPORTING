"""Base classes and enums shared across all models."""

from __future__ import annotations

from sqlalchemy import Enum, MetaData


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Import Base here to avoid circular imports
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = metadata


# Enums
OrgUnitType = Enum(
    "region", "zone", "group", "church", "outreach", name="org_unit_type"
)
ScopeType = Enum("self", "subtree", "custom_set", name="scope_type")
TwoFADelivery = Enum("sms", "email", name="twofa_delivery_type")

# Registry Enums
Gender = Enum("male", "female", "other", name="gender")
MaritalStatus = Enum(
    "single", "married", "divorced", "widowed", "separated", name="marital_status"
)
MembershipStatus = Enum(
    "visitor", "regular", "member", "partner", name="membership_status"
)
FirstTimerStatus = Enum(
    "New", "Contacted", "Returned", "Member", name="first_timer_status"
)
ServiceType = Enum("Sunday", "Midweek", "Special", name="service_type")
DepartmentRoleEnum = Enum("leader", "member", name="department_role")

# Finance Enums
PaymentMethod = Enum(
    "cash", "kingspay", "bank_transfer", "pos", "cheque", "other", name="payment_method"
)
VerifiedStatus = Enum(
    "draft", "verified", "reconciled", "locked", name="verified_status"
)
BatchStatus = Enum("draft", "locked", name="batch_status")
PartnershipCadence = Enum(
    "weekly", "monthly", "quarterly", "annual", name="partnership_cadence"
)
PartnershipStatus = Enum("active", "paused", "ended", name="partnership_status")
SourceType = Enum("manual", "cell_report", name="source_type")

# Cells Enums
MeetingDay = Enum(
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    name="meeting_day"
)
MeetingType = Enum(
    "prayer_planning", "bible_study", "outreach", name="meeting_type"
)
CellReportStatus = Enum(
    "submitted", "reviewed", "approved", name="cell_report_status"
)

