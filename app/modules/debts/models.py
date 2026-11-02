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
from app.shared.constants import (
    CounterpartyType,
    DebtStatus,
    DebtType,
    InterestType,
    RatePeriod,
    RateType,
    enum_values,
)


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
    interest_type: Mapped[InterestType] = mapped_column(
        SqlEnum(
            InterestType,
            name="interest_type_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=InterestType.NONE,
        server_default=InterestType.NONE.value,
    )
    rate_type: Mapped[RateType] = mapped_column(
        SqlEnum(
            RateType,
            name="rate_type_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=RateType.FIXED,
        server_default=RateType.FIXED.value,
    )
    rate_period: Mapped[RatePeriod] = mapped_column(
        SqlEnum(
            RatePeriod,
            name="rate_period_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=RatePeriod.ANNUAL,
        server_default=RatePeriod.ANNUAL.value,
    )
    # Percentage per `rate_period` (e.g. 12.5 means 12.5%).
    interest_rate: Mapped[float] = mapped_column(
        Numeric(7, 4),
        nullable=False,
        default=0,
        server_default="0",
    )

    user = relationship("User", back_populates="debts")
    counterparty = relationship("Counterparty", back_populates="debts")
    payments = relationship(
        "DebtPayment",
        back_populates="debt",
        cascade="all, delete-orphan",
    )
    notification_logs = relationship(
        "NotificationLog",
        back_populates="debt",
        cascade="all, delete-orphan",
    )
    rate_changes = relationship(
        "DebtRateChange",
        back_populates="debt",
        cascade="all, delete-orphan",
        order_by="DebtRateChange.effective_date",
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


class DebtRateChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Rate that applies to a variable-rate debt from `effective_date` onwards."""

    __tablename__ = "debt_rate_changes"
    __table_args__ = (
        CheckConstraint("rate >= 0", name="rate_non_negative"),
        Index(
            "ix_debt_rate_changes_debt_effective_date",
            "debt_id",
            "effective_date",
            unique=True,
        ),
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
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255))

    debt = relationship("Debt", back_populates="rate_changes")
