from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.utils import (
    verify_password,
    create_access_token,
    create_refresh_token,
    generate_2fa_code,
    hash_2fa_code,
)
from app.common.models import (
    User,
    UserSecret,
    LoginSession,
    OrgAssignment,
    Role,
    Permission,
    RolePermission,
)
from app.jobs.notifications import enqueue_2fa_notification


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        stmt = select(User).where(User.email == email, User.is_active.is_(True))
        user = db.execute(stmt).scalar_one_or_none()
        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def send_2fa_code(db: Session, user_id: UUID, delivery_method: str) -> bool:
        user = db.get(User, user_id)
        if not user:
            return False

        code = generate_2fa_code()
        code_hash = hash_2fa_code(code)

        secret = db.execute(
            select(UserSecret).where(UserSecret.user_id == user_id)
        ).scalar_one_or_none()

        if not secret:
            secret = UserSecret(
                user_id=user_id,
                twofa_delivery=delivery_method,
                email=user.email,
            )
            db.add(secret)
        elif secret.twofa_delivery != delivery_method:
            secret.twofa_delivery = delivery_method

        secret.twofa_secret_hash = code_hash
        secret.last_verified_at = None
        db.commit()

        # Create and enqueue notification for email/SMS delivery
        secret_obj = db.execute(
            select(UserSecret).where(UserSecret.user_id == user_id)
        ).scalar_one_or_none()

        phone = secret_obj.phone if secret_obj else None
        enqueue_2fa_notification(
            db=db,
            email=user.email,
            phone=phone,
            code=code,
            delivery_method=delivery_method,
        )

        return True

    @staticmethod
    def verify_2fa_code(db: Session, user_id: UUID, code: str) -> bool:
        secret = db.execute(
            select(UserSecret).where(UserSecret.user_id == user_id)
        ).scalar_one_or_none()

        if not secret or not secret.twofa_secret_hash:
            return False

        provided_hash = hash_2fa_code(code)
        if provided_hash != secret.twofa_secret_hash:
            return False

        # Codes are valid for 5 minutes from when they were sent
        if secret.sent_at is None:
            return False

        now = datetime.now(timezone.utc)
        code_age = now - secret.sent_at
        if code_age > timedelta(minutes=5):
            return False

        secret.last_verified_at = datetime.now(timezone.utc)
        secret.twofa_secret_hash = None  # One-time use
        db.commit()
        return True

    @staticmethod
    def create_session(db: Session, user_id: UUID) -> tuple[str, str]:
        refresh_token, token_hash = create_refresh_token({"sub": str(user_id)})

        session = LoginSession(
            user_id=user_id,
            refresh_token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(session)
        db.commit()

        access_token = create_access_token(
            {"sub": str(user_id), "user_id": str(user_id)}
        )
        return access_token, refresh_token

    @staticmethod
    def refresh_access_token(
        db: Session, refresh_token: str
    ) -> Optional[tuple[str, str]]:
        from app.auth.utils import verify_token

        payload = verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = UUID(payload["sub"])
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        session = db.execute(
            select(LoginSession).where(
                LoginSession.user_id == user_id,
                LoginSession.refresh_token_hash == token_hash,
                LoginSession.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()

        if not session:
            return None

        # Rotate refresh token
        new_refresh, new_hash = create_refresh_token({"sub": str(user_id)})
        session.refresh_token_hash = new_hash
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db.commit()

        access_token = create_access_token(
            {"sub": str(user_id), "user_id": str(user_id)}
        )
        return access_token, new_refresh

    @staticmethod
    def revoke_session(db: Session, refresh_token: str) -> bool:
        from app.auth.utils import verify_token

        payload = verify_token(refresh_token)
        if not payload:
            return False

        user_id = UUID(payload["sub"])
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        session = db.execute(
            select(LoginSession).where(
                LoginSession.user_id == user_id,
                LoginSession.refresh_token_hash == token_hash,
            )
        ).scalar_one_or_none()

        if session:
            db.delete(session)
            db.commit()
        return True

    @staticmethod
    def get_user_permissions(db: Session, user_id: UUID, tenant_id: UUID) -> list[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(OrgAssignment, OrgAssignment.role_id == Role.id)
            .where(
                OrgAssignment.user_id == user_id, OrgAssignment.tenant_id == tenant_id
            )
            .distinct()
        )
        return [code for code in db.execute(stmt).scalars().all()]

    @staticmethod
    def get_user_info(db: Session, user_id: UUID, tenant_id: UUID) -> dict:
        user = db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        # Get assignments with roles
        stmt = (
            select(OrgAssignment)
            .options(joinedload(OrgAssignment.role))
            .where(
                OrgAssignment.user_id == user_id, OrgAssignment.tenant_id == tenant_id
            )
        )
        assignments = db.execute(stmt).scalars().all()

        perms = AuthService.get_user_permissions(db, user_id, tenant_id)

        return {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "is_2fa_enabled": user.is_2fa_enabled,
            "roles": [
                {
                    "role_id": str(assn.role_id),
                    "role_name": assn.role.name if assn.role else None,
                    "org_unit_id": str(assn.org_unit_id),
                    "scope_type": assn.scope_type,
                }
                for assn in assignments
            ],
            "permissions": perms,
            "org_assignments": [
                {
                    "id": str(assn.id),
                    "org_unit_id": str(assn.org_unit_id),
                    "role_id": str(assn.role_id),
                    "scope_type": assn.scope_type,
                }
                for assn in assignments
            ],
        }
