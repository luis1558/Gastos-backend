from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FixedPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A payment that repeats every month (rent, internet, subscriptions)."""

    __tablename__ = "fixed_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="valid_day_of_month"),
        Index("ix_fixed_payments_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    day_of_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    category = relationship("ExpenseCategory")
    payments = relationship(
        "FixedPaymentPayment",
        back_populates="fixed_payment",
        cascade="all, delete-orphan",
    )


class FixedPaymentPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Marks a fixed payment as paid for one month and links the expense it created."""

    __tablename__ = "fixed_payment_payments"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="valid_month"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index(
            "ix_fixed_payment_payments_period",
            "fixed_payment_id",
            "year",
            "month",
            unique=True,
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fixed_payment_id: Mapped[str] = mapped_column(
        ForeignKey("fixed_payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    expense_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"),
    )

    fixed_payment = relationship("FixedPayment", back_populates="payments")
