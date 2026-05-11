from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Optional

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days,
    )
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.jwt_refresh_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(
        token=token,
        secret_key=settings.jwt_secret_key,
        expected_type="access",
    )


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(
        token=token,
        secret_key=settings.jwt_refresh_secret_key,
        expected_type="refresh",
    )


def _decode_token(
    token: str,
    secret_key: str,
    expected_type: str,
) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
    token_type = payload.get("type")
    subject = payload.get("sub")

    if token_type != expected_type or not isinstance(subject, str):
        raise JWTError("Invalid token payload")

    return payload


def get_token_subject(payload: dict[str, Any]) -> Optional[str]:
    subject = payload.get("sub")
    if isinstance(subject, str):
        return subject
    return None
