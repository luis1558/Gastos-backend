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
from app.shared.constants import GoalKind, GoalStatus, enum_values


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Money set aside for something. It never leaves the account: it only stops being available."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_amount_positive"),
        Index("ix_goals_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[GoalKind] = mapped_column(
        SqlEnum(GoalKind, name="goal_kind_enum", values_callable=enum_values),
        nullable=False,
    )
    status: Mapped[GoalStatus] = mapped_column(
        SqlEnum(GoalStatus, name="goal_status_enum", values_callable=enum_values),
        nullable=False,
        default=GoalStatus.ACTIVE,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    debt_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("debts.id", ondelete="SET NULL"),
        index=True,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    debt = relationship("Debt")
    contributions = relationship(
        "GoalContribution",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="GoalContribution.contribution_date.desc()",
    )


class GoalContribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Signed movement into (positive) or out of (negative) a goal's pocket."""

    __tablename__ = "goal_contributions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        Index("ix_goal_contributions_goal_date", "goal_id", "contribution_date"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_id: Mapped[str] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contribution_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255))

    goal = relationship("Goal", back_populates="contributions")
