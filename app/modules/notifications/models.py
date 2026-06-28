from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin
from app.shared.constants import enum_values


class ReminderType(str, enum.Enum):
    SEVEN_DAYS = "seven_days"
    THREE_DAYS = "three_days"
    DUE_DATE = "due_date"


class NotificationLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notification_logs_debt_reminder", "debt_id", "reminder_type", unique=True),
    )

    debt_id: Mapped[str] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_type: Mapped[ReminderType] = mapped_column(
        SqlEnum(
            ReminderType,
            name="reminder_type_enum",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    debt = relationship("Debt", back_populates="notification_logs")
