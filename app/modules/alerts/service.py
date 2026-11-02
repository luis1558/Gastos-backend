from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.alerts.schemas import AlertItem, AlertsResponse
from app.modules.cards.repository import CardRepository
from app.modules.debts.interest import balance_for_debt
from app.modules.debts.repository import DebtRepository
from app.modules.fixed_payments.repository import FixedPaymentRepository
from app.modules.fixed_payments.service import due_date_for
from app.modules.goals.repository import GoalRepository
from app.modules.users.models import User
from app.shared.constants import DebtStatus, DebtType, GoalKind, GoalStatus

ZERO = Decimal("0")


def _severity(days_left: int) -> str:
    if days_left < 0:
        return "overdue"
    if days_left == 0:
        return "today"
    return "soon"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


class AlertService:
    """Builds the upcoming-due list on the fly from the user's data.

    Nothing is stored: paying or completing something makes its alert disappear by itself.
    `today` comes from the client so the day follows the user's timezone, not the server's.
    """

    def __init__(self, db: Session) -> None:
        self.debts = DebtRepository(db)
        self.fixed_payments = FixedPaymentRepository(db)
        self.cards = CardRepository(db)
        self.goals = GoalRepository(db)

    def get_alerts(self, current_user: User, today: date, days: int) -> AlertsResponse:
        horizon = today + timedelta(days=days)
        active_goals = self.goals.list_goals(current_user.id, GoalStatus.ACTIVE)
        saved_by_link: dict[tuple[str, str], Decimal] = {}
        for goal in active_goals:
            link = self._goal_link(goal)
            if link is not None:
                saved_by_link[link] = sum((Decimal(str(c.amount)) for c in goal.contributions), ZERO)

        items: list[AlertItem] = []
        items += self._debt_alerts(current_user.id, today, horizon, saved_by_link)
        items += self._fixed_payment_alerts(current_user.id, today, horizon, saved_by_link)
        items += self._card_alerts(current_user.id, today, horizon, saved_by_link)
        items += self._goal_alerts(active_goals, today, horizon)

        # Overdue first (oldest first), then the closest due dates.
        items.sort(key=lambda item: (item.days_left >= 0, item.days_left, item.title))
        return AlertsResponse(
            items=items,
            total=len(items),
            overdue=sum(1 for item in items if item.severity == "overdue"),
        )

    @staticmethod
    def _goal_link(goal) -> Optional[tuple[str, str]]:
        if goal.kind == GoalKind.DEBT and goal.debt_id:
            return ("debt", goal.debt_id)
        if goal.kind == GoalKind.FIXED_PAYMENT and goal.fixed_payment_id:
            return ("fixed_payment", goal.fixed_payment_id)
        if goal.kind == GoalKind.CARD and goal.card_id:
            return ("card", goal.card_id)
        return None

    def _debt_alerts(self, user_id, today, horizon, saved_by_link) -> list[AlertItem]:
        alerts: list[AlertItem] = []
        for debt in self.debts.list_debts(user_id, DebtType.PAYABLE, None):
            if debt.status not in (DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID):
                continue
            if debt.due_date is None or debt.due_date > horizon:
                continue
            days_left = (debt.due_date - today).days
            alerts.append(
                AlertItem(
                    id=f"debt:{debt.id}:{debt.due_date.isoformat()}",
                    kind="debt",
                    entity_id=debt.id,
                    title=debt.description,
                    detail=debt.counterparty.name,
                    amount=balance_for_debt(debt, today).total_owed,
                    due_date=debt.due_date,
                    days_left=days_left,
                    severity=_severity(days_left),
                    saved_amount=saved_by_link.get(("debt", debt.id)),
                )
            )
        return alerts

    def _fixed_payment_alerts(self, user_id, today, horizon, saved_by_link) -> list[AlertItem]:
        alerts: list[AlertItem] = []
        months = [(today.year, today.month), _next_month(today.year, today.month)]
        for payment in self.fixed_payments.list_fixed_payments(user_id):
            if not payment.is_active:
                continue
            for year, month in months:
                due = due_date_for(year, month, payment.day_of_month)
                if due > horizon or self._created_after(payment, due):
                    continue
                if any(p.year == year and p.month == month for p in payment.payments):
                    continue
                days_left = (due - today).days
                alerts.append(
                    AlertItem(
                        id=f"fixed_payment:{payment.id}:{due.isoformat()}",
                        kind="fixed_payment",
                        entity_id=payment.id,
                        title=payment.name,
                        detail=payment.category.name,
                        amount=Decimal(str(payment.amount)),
                        due_date=due,
                        days_left=days_left,
                        severity=_severity(days_left),
                        saved_amount=saved_by_link.get(("fixed_payment", payment.id)),
                    )
                )
        return alerts

    def _card_alerts(self, user_id, today, horizon, saved_by_link) -> list[AlertItem]:
        alerts: list[AlertItem] = []
        months = [(today.year, today.month), _next_month(today.year, today.month)]
        for card in self.cards.list_cards(user_id):
            if not card.is_active:
                continue
            label = f"{card.name} ····{card.last_four}" if card.last_four else card.name
            for year, month in months:
                due = due_date_for(year, month, card.payment_day)
                if due > horizon or self._created_after(card, due):
                    continue
                statement = next((s for s in card.statements if s.year == year and s.month == month), None)
                if statement is not None and statement.paid_on is not None:
                    continue
                days_left = (due - today).days
                alerts.append(
                    AlertItem(
                        id=f"card:{card.id}:{due.isoformat()}",
                        kind="card",
                        entity_id=card.id,
                        title=label,
                        detail=None if statement is not None else "Falta anotar el monto del extracto",
                        amount=Decimal(str(statement.amount)) if statement is not None else None,
                        due_date=due,
                        days_left=days_left,
                        severity=_severity(days_left),
                        saved_amount=saved_by_link.get(("card", card.id)),
                    )
                )
        return alerts

    def _goal_alerts(self, goals, today, horizon) -> list[AlertItem]:
        """Goals with a date that are not fully funded. Goals linked to a debt, card or fixed
        payment are folded into that item's alert (`saved_amount`) instead of repeating it."""
        alerts: list[AlertItem] = []
        for goal in goals:
            if goal.target_date is None or goal.target_date > horizon or self._goal_link(goal) is not None:
                continue
            saved = sum((Decimal(str(c.amount)) for c in goal.contributions), ZERO)
            remaining = Decimal(str(goal.target_amount)) - saved
            if remaining <= ZERO:
                continue
            days_left = (goal.target_date - today).days
            alerts.append(
                AlertItem(
                    id=f"goal:{goal.id}:{goal.target_date.isoformat()}",
                    kind="goal",
                    entity_id=goal.id,
                    title=goal.name,
                    detail="Meta",
                    amount=remaining,
                    due_date=goal.target_date,
                    days_left=days_left,
                    severity=_severity(days_left),
                    saved_amount=saved,
                )
            )
        return alerts

    @staticmethod
    def _created_after(entity, due: date) -> bool:
        """Items created after their due date for a month never existed for it, so they were not missed."""
        return entity.created_at.date() > due
