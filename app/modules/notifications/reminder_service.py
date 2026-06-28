from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.notifications.email_service import ReminderEmailData, send_reminder_email
from app.modules.notifications.models import ReminderType
from app.modules.notifications.repository import NotificationRepository

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


def _format_amount(value: Decimal) -> str:
    return f"${value:,.2f}"


REMINDER_SCHEDULE: list[tuple[int, ReminderType, str]] = [
    (7, ReminderType.SEVEN_DAYS, "seven_days"),
    (3, ReminderType.THREE_DAYS, "three_days"),
    (0, ReminderType.DUE_DATE, "due_date"),
]


def _paid_amount(debt) -> Decimal:
    total = ZERO
    for payment in debt.payments:
        total += Decimal(str(payment.amount))
    return total


async def check_and_send_reminders(db: Session) -> None:
    repo = NotificationRepository(db)
    today = date.today()

    for days_before, reminder_type, type_key in REMINDER_SCHEDULE:
        target_date = today + timedelta(days=days_before)
        debts = repo.find_debts_due_on(target_date)

        for debt in debts:
            if repo.reminder_already_sent(debt.id, reminder_type):
                continue

            user_info = repo.get_user_email_and_name(debt)
            if user_info is None:
                continue

            user_email, user_name = user_info
            paid = _paid_amount(debt)
            original = Decimal(str(debt.original_amount))
            remaining = original - paid

            data = ReminderEmailData(
                user_email=user_email,
                user_name=user_name,
                debt_description=debt.description,
                counterparty_name=debt.counterparty.name,
                original_amount=_format_amount(original),
                paid_amount=_format_amount(paid),
                remaining_amount=_format_amount(remaining),
                due_date=debt.due_date.isoformat() if debt.due_date else "Sin fecha",
                reminder_type_label=f"{days_before} días antes del vencimiento" if days_before > 0 else "Vence hoy",
            )

            try:
                await send_reminder_email(data, type_key)
                repo.log_reminder(debt.id, reminder_type)
                db.commit()
                logger.info("Reminder sent for debt %s (%s)", debt.id, type_key)
            except Exception:
                logger.exception("Failed to send reminder for debt %s", debt.id)
                db.rollback()
