from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.expenses.models import Expense
from app.modules.expenses.repository import ExpenseRepository
from app.modules.fixed_payments.models import FixedPayment, FixedPaymentPayment
from app.modules.fixed_payments.repository import FixedPaymentRepository
from app.modules.fixed_payments.schemas import FixedPaymentResponse
from app.modules.goals.repository import GoalRepository
from app.modules.users.models import User
from app.shared.constants import GoalStatus

EDITABLE_FIELDS = {"name", "amount", "day_of_month", "category_id", "notes", "is_active"}


def due_date_for(year: int, month: int, day_of_month: int) -> date:
    """Day of the month, clamped for short months (the 31st becomes the 28th/29th/30th)."""
    return date(year, month, min(day_of_month, calendar.monthrange(year, month)[1]))


class FixedPaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FixedPaymentRepository(db)
        self.expense_repository = ExpenseRepository(db)
        self.goal_repository = GoalRepository(db)

    def list_fixed_payments(self, current_user: User, year: int, month: int) -> list[FixedPaymentResponse]:
        items = self.repository.list_fixed_payments(current_user.id)
        return [self._to_response(item, year, month) for item in items]

    def create_fixed_payment(
        self,
        current_user: User,
        name: str,
        amount: Decimal,
        day_of_month: int,
        category_id: str,
        notes: Optional[str],
    ) -> FixedPaymentResponse:
        category = self._require_category(current_user.id, category_id)
        fixed_payment = FixedPayment(
            user_id=current_user.id,
            category_id=category.id,
            name=name.strip(),
            amount=amount,
            day_of_month=day_of_month,
            notes=notes,
            is_active=True,
        )
        self.repository.save_fixed_payment(fixed_payment)
        self.db.commit()
        today = date.today()
        return self._to_response(self._require(current_user.id, fixed_payment.id), today.year, today.month)

    def update_fixed_payment(
        self,
        current_user: User,
        fixed_payment_id: str,
        changes: dict[str, Any],
        year: int,
        month: int,
    ) -> FixedPaymentResponse:
        fixed_payment = self._require(current_user.id, fixed_payment_id)
        for field, value in changes.items():
            if field not in EDITABLE_FIELDS:
                continue
            if value is None and field != "notes":
                continue
            if field == "category_id":
                value = self._require_category(current_user.id, value).id
            if field == "name":
                value = value.strip()
            setattr(fixed_payment, field, value)
        self.repository.save_fixed_payment(fixed_payment)
        self.db.commit()
        return self._to_response(self._require(current_user.id, fixed_payment_id), year, month)

    def delete_fixed_payment(self, current_user: User, fixed_payment_id: str) -> None:
        """Removes the fixed payment. Expenses it already created are kept."""
        fixed_payment = self._require(current_user.id, fixed_payment_id)
        self.repository.delete_fixed_payment(fixed_payment)
        self.db.commit()

    def pay(
        self,
        current_user: User,
        fixed_payment_id: str,
        year: int,
        month: int,
        amount: Optional[Decimal],
        paid_on: date,
    ) -> FixedPaymentResponse:
        """Marks the month as paid and records the matching expense."""
        fixed_payment = self._require(current_user.id, fixed_payment_id)
        if not fixed_payment.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This fixed payment is inactive.",
            )
        if self.repository.get_period_payment(fixed_payment.id, year, month):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This fixed payment is already paid for that month.",
            )

        paid_amount = amount if amount is not None else Decimal(str(fixed_payment.amount))
        expense = Expense(
            user_id=current_user.id,
            category_id=fixed_payment.category_id,
            expense_date=paid_on,
            year=year,
            month=month,
            amount=paid_amount,
            description=fixed_payment.name,
            notes=fixed_payment.notes,
        )
        self.expense_repository.save_expense(expense)
        self.repository.save_period_payment(
            FixedPaymentPayment(
                user_id=current_user.id,
                fixed_payment_id=fixed_payment.id,
                year=year,
                month=month,
                amount=paid_amount,
                paid_on=paid_on,
                expense_id=expense.id,
            )
        )

        # The money now left as an expense, so the goal saving for it must stop reserving it.
        goal = self.goal_repository.get_active_goal_for_fixed_payment(current_user.id, fixed_payment.id)
        if goal is not None:
            goal.status = GoalStatus.COMPLETED
            goal.closed_at = datetime.now(timezone.utc)
            self.goal_repository.save_goal(goal)

        self.db.commit()
        # The new payment was added directly, so the already-loaded collection is stale.
        self.db.expire(fixed_payment, ["payments"])
        return self._to_response(fixed_payment, year, month)

    def undo_payment(self, current_user: User, fixed_payment_id: str, year: int, month: int) -> None:
        """Reverts a payment: removes the record and the expense it created."""
        fixed_payment = self._require(current_user.id, fixed_payment_id)
        payment = self.repository.get_period_payment(fixed_payment.id, year, month)
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="There is no payment registered for that month.",
            )
        if payment.expense_id:
            expense = self.expense_repository.get_expense(current_user.id, payment.expense_id)
            if expense is not None:
                self.expense_repository.delete_expense(expense)
        self.repository.delete_period_payment(payment)
        self.db.commit()

    def _require(self, user_id: str, fixed_payment_id: str) -> FixedPayment:
        fixed_payment = self.repository.get_fixed_payment(user_id, fixed_payment_id)
        if fixed_payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fixed payment not found.",
            )
        return fixed_payment

    def _require_category(self, user_id: str, category_id: str):
        category = self.expense_repository.get_category_by_id(user_id, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found.",
            )
        return category

    @staticmethod
    def _to_response(fixed_payment: FixedPayment, year: int, month: int) -> FixedPaymentResponse:
        paid = next((p for p in fixed_payment.payments if p.year == year and p.month == month), None)
        return FixedPaymentResponse(
            id=fixed_payment.id,
            name=fixed_payment.name,
            amount=Decimal(str(fixed_payment.amount)),
            day_of_month=fixed_payment.day_of_month,
            category_id=fixed_payment.category_id,
            category_name=fixed_payment.category.name,
            notes=fixed_payment.notes,
            is_active=fixed_payment.is_active,
            due_date=due_date_for(year, month, fixed_payment.day_of_month),
            status="paid" if paid else "pending",
            paid_amount=Decimal(str(paid.amount)) if paid else None,
            paid_on=paid.paid_on if paid else None,
        )
