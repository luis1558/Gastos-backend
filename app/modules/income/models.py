from __future__ import annotations

from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MonthlyIncomeConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monthly_income_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "year", "month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="valid_month"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="valid_year"),
        CheckConstraint("base_income >= 0", name="base_income_non_negative"),
        CheckConstraint("extra_income >= 0", name="extra_income_non_negative"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    base_income: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    extra_income: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="monthly_income_configs")
