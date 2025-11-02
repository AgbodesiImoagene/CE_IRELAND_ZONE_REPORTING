from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    MetaData,
    String,
    Boolean,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    Integer,
    JSON,
    TIMESTAMP,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


# Enums
OrgUnitType = Enum(
    "region", "zone", "group", "church", "outreach", name="org_unit_type"
)
ScopeType = Enum("self", "subtree", "custom_set", name="scope_type")
TwoFADelivery = Enum("sms", "email", name="twofa_delivery_type")


# Core IAM models
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    code: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500))


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )


class OrgUnit(Base):
    __tablename__ = "org_units"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(OrgUnitType, nullable=False)
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("org_units.id", ondelete="SET NULL")
    )


class OrgAssignment(Base):
    __tablename__ = "org_assignments"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(ScopeType, nullable=False, default="self")

    role: Mapped[Optional[Role]] = relationship("Role", back_populates=None)

    __table_args__ = (
        Index("ix_org_assignments_user_org", "user_id", "org_unit_id", unique=False),
    )


class OrgAssignmentUnit(Base):
    __tablename__ = "org_assignment_units"

    assignment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_assignments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        primary_key=True,
    )


class UserIdentity(Base):
    __tablename__ = "user_identities"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_identity_provider_uid"
        ),
    )


class UserSecret(Base):
    __tablename__ = "user_secrets"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    twofa_delivery: Mapped[str] = mapped_column(
        TwoFADelivery, nullable=False, default="email"
    )
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    twofa_secret_hash: Mapped[Optional[str]] = mapped_column(String(255))
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    __table_args__ = (Index("ix_login_sessions_user_id", "user_id"),)


class OutboxNotification(Base):
    __tablename__ = "outbox_notifications"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # invite, 2fa_code
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    delivery_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(String(500))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id"), nullable=False
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("org_units.id"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(ScopeType, nullable=False, default="self")
    twofa_delivery: Mapped[str] = mapped_column(
        TwoFADelivery, nullable=False, default="email"
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )

    __table_args__ = (Index("ix_user_invitations_email_tenant", "email", "tenant_id"),)


class UserInvitationUnit(Base):
    """Custom org units for invitations with custom_set scope."""

    __tablename__ = "user_invitation_units"

    invitation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_invitations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        primary_key=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    actor_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    before_json: Mapped[Optional[dict]] = mapped_column(JSON)
    after_json: Mapped[Optional[dict]] = mapped_column(JSON)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc)
    )
