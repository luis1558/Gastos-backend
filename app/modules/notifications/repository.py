from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.modules.debts.models import Debt
from app.modules.notifications.models import NotificationLog, ReminderType
from app.shared.constants import DebtStatus


class NotificationRepository:
    def __init__(self, db) -> None:
        self.db = db

    def find_debts_due_on(self, target_date: date) -> list[Debt]:
        stmt: Select[tuple[Debt]] = (
            select(Debt)
            .options(
                selectinload(Debt.counterparty),
                selectinload(Debt.payments),
            )
            .where(
                Debt.due_date == target_date,
                Debt.status.in_([DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID]),
            )
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def reminder_already_sent(self, debt_id: str, reminder_type: ReminderType) -> bool:
        stmt: Select[tuple[NotificationLog]] = select(NotificationLog).where(
            NotificationLog.debt_id == debt_id,
            NotificationLog.reminder_type == reminder_type,
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def log_reminder(self, debt_id: str, reminder_type: ReminderType) -> NotificationLog:
        log = NotificationLog(debt_id=debt_id, reminder_type=reminder_type)
        self.db.add(log)
        self.db.flush()
        return log

    def get_user_email_and_name(self, debt: Debt) -> Optional[tuple[str, str]]:
        from app.modules.users.models import User

        stmt: Select[tuple[User]] = select(User).where(User.id == debt.user_id)
        user = self.db.execute(stmt).scalar_one_or_none()
        if user is None:
            return None
        return user.email, user.full_name or user.email
