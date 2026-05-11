from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshToken
from app.modules.users.models import User


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        stmt: Select[tuple[User]] = select(User).where(User.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        stmt: Select[tuple[User]] = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: Optional[str],
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        self.db.add(user)

    def create_refresh_token(
        self,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(refresh_token)
        self.db.flush()
        return refresh_token

    def get_refresh_token(self, token_hash: str) -> Optional[RefreshToken]:
        stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def revoke_refresh_token(self, refresh_token: RefreshToken) -> None:
        refresh_token.revoked_at = datetime.now(timezone.utc)
        self.db.add(refresh_token)
