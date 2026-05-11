from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.constants import PaymentMethod, enum_values


class ExpenseCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("user_id", "slug"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(32))
    icon: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    user = relationship("User", back_populates="expense_categories")
    expenses = relationship("Expense", back_populates="category")


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="valid_month"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="valid_year"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_expenses_user_year_month", "user_id", "year", "month"),
        Index("ix_expenses_user_expense_date", "user_id", "expense_date"),
        Index("ix_expenses_user_category_id", "user_id", "category_id"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_method: Mapped[Optional[PaymentMethod]] = mapped_column(
        SqlEnum(
            PaymentMethod,
            name="payment_method_enum",
            values_callable=enum_values,
        ),
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="expenses")
    category = relationship("ExpenseCategory", back_populates="expenses")
