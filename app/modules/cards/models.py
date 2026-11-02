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


class Card(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A credit card whose monthly bill the user wants to track and pay."""

    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("payment_day BETWEEN 1 AND 31", name="valid_payment_day"),
        Index("ix_cards_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Needed only when paying the card must create an expense (purchases are not tracked).
    category_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_four: Mapped[Optional[str]] = mapped_column(String(4))
    payment_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # True: each purchase is already an expense, so paying the bill must not create another one.
    tracks_purchases: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    category = relationship("ExpenseCategory")
    statements = relationship(
        "CardStatement",
        back_populates="card",
        cascade="all, delete-orphan",
    )


class CardStatement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The amount due on a card for one month, as written on the bank statement."""

    __tablename__ = "card_statements"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="valid_month"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_card_statements_period", "card_id", "year", "month", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    paid_on: Mapped[Optional[date]] = mapped_column(Date)
    expense_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"),
    )

    card = relationship("Card", back_populates="statements")
