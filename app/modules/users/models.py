from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    monthly_income_configs = relationship(
        "MonthlyIncomeConfig",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    expense_categories = relationship(
        "ExpenseCategory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    expenses = relationship(
        "Expense",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    counterparties = relationship(
        "Counterparty",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    debts = relationship(
        "Debt",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    debt_payments = relationship(
        "DebtPayment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
