"""Registry domain models (people, memberships, services, attendance, departments)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    Integer,
    TIMESTAMP,
    Uuid,
    Date,
    Time,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import (
    Base,
    Gender,
    MaritalStatus,
    MembershipStatus,
    FirstTimerStatus,
    DepartmentRoleEnum,
)


class People(Base):
    """People (members and visitors) table."""

    __tablename__ = "people"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_code: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[Optional[str]] = mapped_column(String(20))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(100))
    dob: Mapped[Optional[datetime]] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(Gender, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(320))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    address_line1: Mapped[Optional[str]] = mapped_column(String(200))
    address_line2: Mapped[Optional[str]] = mapped_column(String(200))
    town: Mapped[Optional[str]] = mapped_column(String(100))
    county: Mapped[Optional[str]] = mapped_column(String(100))
    eircode: Mapped[Optional[str]] = mapped_column(String(10))
    marital_status: Mapped[Optional[str]] = mapped_column(MaritalStatus)
    consent_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_data_storage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "member_code", name="uq_people_tenant_member_code"),
        Index("ix_people_tenant_org", "tenant_id", "org_unit_id"),
    )


class Membership(Base):
    """Membership status and details for people."""

    __tablename__ = "memberships"

    person_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(MembershipStatus, nullable=False, default="visitor")
    join_date: Mapped[Optional[datetime]] = mapped_column(Date)
    foundation_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    baptism_date: Mapped[Optional[datetime]] = mapped_column(Date)
    cell_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cells.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (Index("ix_memberships_cell_id", "cell_id"),)


class FirstTimer(Base):
    """First-timer visitor tracking."""

    __tablename__ = "first_timers"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    person_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[Optional[str]] = mapped_column(String(200))  # inviter/source
    status: Mapped[str] = mapped_column(
        FirstTimerStatus, nullable=False, default="New"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Service(Base):
    """Service scheduling (Sunday, Midweek, Special)."""

    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # Sunday, Midweek, Special or text
    service_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    service_time: Mapped[Optional[datetime]] = mapped_column(Time)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "org_unit_id", "service_date", "name",
            name="uq_services_tenant_org_date_name"
        ),
        Index("ix_services_tenant_org", "tenant_id", "org_unit_id"),
    )


class Attendance(Base):
    """Attendance records for services (one per service)."""

    __tablename__ = "attendance"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    men_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    women_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    teens_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kids_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_timers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_converts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_attendance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "service_id", name="uq_attendance_tenant_service"),
    )


class Department(Base):
    """Ministry departments within churches."""

    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active, inactive
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_departments_tenant_org", "tenant_id", "org_unit_id"),
    )


class DepartmentRole(Base):
    """Person-to-department role assignments."""

    __tablename__ = "department_roles"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    dept_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(DepartmentRoleEnum, nullable=False)
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)

    __table_args__ = (
        Index("ix_department_roles_dept_person", "dept_id", "person_id"),
    )

