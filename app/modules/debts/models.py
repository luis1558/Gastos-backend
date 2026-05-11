from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.constants import CounterpartyType, DebtStatus, DebtType, enum_values


class Counterparty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "counterparties"
    __table_args__ = (
        Index("ix_counterparties_user_name", "user_id", "name"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[Optional[CounterpartyType]] = mapped_column(
        SqlEnum(
            CounterpartyType,
            name="counterparty_type_enum",
            values_callable=enum_values,
        ),
    )
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="counterparties")
    debts = relationship("Debt", back_populates="counterparty")


class Debt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="original_amount_positive"),
        Index("ix_debts_user_type_status", "user_id", "type", "status"),
        Index("ix_debts_user_origin_date", "user_id", "origin_date"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counterparty_id: Mapped[str] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[DebtType] = mapped_column(
        SqlEnum(
            DebtType,
            name="debt_type_enum",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[DebtStatus] = mapped_column(
        SqlEnum(
            DebtStatus,
            name="debt_status_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=DebtStatus.PENDING,
    )
    origin_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    original_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="debts")
    counterparty = relationship("Counterparty", back_populates="debts")
    payments = relationship(
        "DebtPayment",
        back_populates="debt",
        cascade="all, delete-orphan",
    )


class DebtPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "debt_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_debt_payments_debt_payment_date", "debt_id", "payment_date"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    debt_id: Mapped[str] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    user = relationship("User", back_populates="debt_payments")
    debt = relationship("Debt", back_populates="payments")
