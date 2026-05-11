from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_token_subject,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AuthResponse, TokenPairResponse
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AuthRepository(db)

    def register(
        self,
        email: str,
        password: str,
        full_name: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> AuthResponse:
        existing_user = self.repository.get_user_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with that email already exists.",
            )

        user = self.repository.create_user(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
        )
        self.repository.update_last_login(user)
        tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        self.db.commit()
        self.db.refresh(user)
        return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)

    def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> AuthResponse:
        user = self.repository.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        self.repository.update_last_login(user)
        tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        self.db.commit()
        self.db.refresh(user)
        return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)

    def refresh_session(
        self,
        refresh_token: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> TokenPairResponse:
        try:
            payload = decode_refresh_token(refresh_token)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
            ) from exc

        subject = get_token_subject(payload)
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token subject.",
            )

        stored_token = self.repository.get_refresh_token(hash_token(refresh_token))
        self._validate_stored_refresh_token(stored_token)

        user = self.repository.get_user_by_id(subject)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not available for refresh.",
            )

        self.repository.revoke_refresh_token(stored_token)
        tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        self.db.commit()
        return tokens

    def get_current_user(self, access_token: str) -> User:
        try:
            payload = decode_access_token(access_token)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
            ) from exc

        subject = get_token_subject(payload)
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token subject.",
            )

        user = self.repository.get_user_by_id(subject)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive.",
            )
        return user

    def _issue_tokens(
        self,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> TokenPairResponse:
        access_token = create_access_token(user.id)
        refresh_token, refresh_expires_at = create_refresh_token(user.id)
        self.repository.create_refresh_token(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=refresh_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_in=settings.access_token_expire_minutes * 60,
            refresh_token_expires_at=refresh_expires_at,
        )

    def _validate_stored_refresh_token(
        self,
        stored_token: Optional[RefreshToken],
    ) -> None:
        now = datetime.now(timezone.utc)
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not recognized.",
            )
        if stored_token.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token already revoked.",
            )
        if stored_token.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired.",
            )
