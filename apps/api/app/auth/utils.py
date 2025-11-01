from __future__ import annotations

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        default_expire = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + default_expire
    to_encode.update({
        "exp": expire,
        "type": "access",
        "nonce": secrets.token_urlsafe(16),  # Random nonce for uniqueness
    })
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> tuple[str, str]:
    expire_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expire_delta
    to_encode = data.copy()
    # Add a nonce to ensure uniqueness even if called in same microsecond
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "nonce": secrets.token_urlsafe(16),  # Random nonce for uniqueness
    })
    token = jwt.encode(to_encode, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_2fa_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def hash_2fa_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
