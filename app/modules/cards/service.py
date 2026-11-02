from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.cards.models import Card, CardStatement
from app.modules.cards.repository import CardRepository
from app.modules.cards.schemas import CardPurchaseResponse, CardResponse
from app.modules.expenses.models import Expense
from app.modules.expenses.repository import ExpenseRepository
from app.modules.fixed_payments.service import due_date_for
from app.modules.goals.repository import GoalRepository
from app.modules.users.models import User
from app.shared.constants import GoalStatus

EDITABLE_FIELDS = {"name", "last_four", "payment_day", "tracks_purchases", "category_id", "notes", "is_active"}


class CardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CardRepository(db)
        self.expense_repository = ExpenseRepository(db)
        self.goal_repository = GoalRepository(db)

    def list_cards(self, current_user: User, year: int, month: int) -> list[CardResponse]:
        summary = self.repository.purchases_summary(current_user.id, year, month)
        return [
            self._to_response(card, year, month, summary.get(card.id))
            for card in self.repository.list_cards(current_user.id)
        ]

    def list_purchases(self, current_user: User, card_id: str, year: int, month: int) -> list[CardPurchaseResponse]:
        card = self._require(current_user.id, card_id)
        return [
            CardPurchaseResponse(
                id=expense.id,
                expense_date=expense.expense_date,
                amount=Decimal(str(expense.amount)),
                description=expense.description,
                category_name=expense.category.name,
            )
            for expense in self.repository.list_purchases(current_user.id, card.id, year, month)
        ]

    def _respond(self, user_id: str, card: Card, year: int, month: int) -> CardResponse:
        summary = self.repository.purchases_summary(user_id, year, month, card_id=card.id)
        return self._to_response(card, year, month, summary.get(card.id))

    def create_card(
        self,
        current_user: User,
        name: str,
        last_four: Optional[str],
        payment_day: int,
        tracks_purchases: bool,
        category_id: Optional[str],
        notes: Optional[str],
    ) -> CardResponse:
        category_id = self._validate_category(current_user.id, tracks_purchases, category_id)
        card = Card(
            user_id=current_user.id,
            name=name.strip(),
            last_four=last_four,
            payment_day=payment_day,
            tracks_purchases=tracks_purchases,
            category_id=category_id,
            notes=notes,
            is_active=True,
        )
        self.repository.save_card(card)
        self.db.commit()
        today = date.today()
        return self._respond(current_user.id, self._require(current_user.id, card.id), today.year, today.month)

    def update_card(
        self,
        current_user: User,
        card_id: str,
        changes: dict[str, Any],
        year: int,
        month: int,
    ) -> CardResponse:
        card = self._require(current_user.id, card_id)
        for field, value in changes.items():
            if field not in EDITABLE_FIELDS:
                continue
            if value is None and field not in {"notes", "last_four", "category_id"}:
                continue
            if field == "name":
                value = value.strip()
            setattr(card, field, value)
        if not card.tracks_purchases and self.repository.count_purchases(current_user.id, card.id) > 0:
            # Paying a payment-only card creates an expense, which would duplicate its registered purchases.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This card has registered purchases. Remove them before switching to payment-only tracking.",
            )
        card.category_id = self._validate_category(current_user.id, card.tracks_purchases, card.category_id)
        self.repository.save_card(card)
        self.db.commit()
        # The category may have changed, so the already-loaded relationship is stale.
        self.db.expire(card, ["category"])
        return self._respond(current_user.id, card, year, month)

    def delete_card(self, current_user: User, card_id: str) -> None:
        """Removes the card and its statements. Expenses already created are kept."""
        card = self._require(current_user.id, card_id)
        self.repository.delete_card(card)
        self.db.commit()

    def set_statement(
        self, current_user: User, card_id: str, year: int, month: int, amount: Decimal
    ) -> CardResponse:
        card = self._require(current_user.id, card_id)
        statement = self.repository.get_statement(card.id, year, month)
        if statement is not None and statement.paid_on is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The card is already paid for that month. Undo the payment to change the amount.",
            )
        if statement is None:
            statement = CardStatement(user_id=current_user.id, card_id=card.id, year=year, month=month, amount=amount)
        else:
            statement.amount = amount
        self.repository.save_statement(statement)
        self.db.commit()
        self.db.expire(card, ["statements"])
        return self._respond(current_user.id, card, year, month)

    def clear_statement(self, current_user: User, card_id: str, year: int, month: int) -> CardResponse:
        card = self._require(current_user.id, card_id)
        statement = self.repository.get_statement(card.id, year, month)
        if statement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="There is no amount registered for that month.",
            )
        if statement.paid_on is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The card is already paid for that month. Undo the payment first.",
            )
        self.repository.delete_statement(statement)
        self.db.commit()
        self.db.expire(card, ["statements"])
        return self._respond(current_user.id, card, year, month)

    def pay(
        self,
        current_user: User,
        card_id: str,
        year: int,
        month: int,
        amount: Optional[Decimal],
        paid_on: date,
    ) -> CardResponse:
        """Marks the month as paid; creates an expense only if purchases are not tracked."""
        card = self._require(current_user.id, card_id)
        if not card.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This card is inactive.")

        statement = self.repository.get_statement(card.id, year, month)
        if statement is not None and statement.paid_on is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This card is already paid for that month.",
            )
        if statement is None and amount is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Write down the amount of the statement before paying.",
            )
        if statement is None:
            statement = CardStatement(user_id=current_user.id, card_id=card.id, year=year, month=month, amount=amount)
        elif amount is not None:
            statement.amount = amount
        paid_amount = Decimal(str(statement.amount))

        if not card.tracks_purchases:
            expense = Expense(
                user_id=current_user.id,
                category_id=card.category_id,
                expense_date=paid_on,
                year=year,
                month=month,
                amount=paid_amount,
                description=f"Pago tarjeta {card.name}",
                notes=card.notes,
            )
            self.expense_repository.save_expense(expense)
            statement.expense_id = expense.id
        statement.paid_on = paid_on
        self.repository.save_statement(statement)

        # The money left the account, so the goal saving for this payment stops reserving it.
        goal = self.goal_repository.get_active_goal_for_card(current_user.id, card.id)
        if goal is not None:
            goal.status = GoalStatus.COMPLETED
            goal.closed_at = datetime.now(timezone.utc)
            self.goal_repository.save_goal(goal)

        self.db.commit()
        self.db.expire(card, ["statements"])
        return self._respond(current_user.id, card, year, month)

    def undo_payment(self, current_user: User, card_id: str, year: int, month: int) -> CardResponse:
        """Reverts a payment: removes the expense it created (if any) and keeps the amount."""
        card = self._require(current_user.id, card_id)
        statement = self.repository.get_statement(card.id, year, month)
        if statement is None or statement.paid_on is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="There is no payment registered for that month.",
            )
        if statement.expense_id:
            expense = self.expense_repository.get_expense(current_user.id, statement.expense_id)
            if expense is not None:
                self.expense_repository.delete_expense(expense)
        statement.expense_id = None
        statement.paid_on = None
        self.repository.save_statement(statement)
        self.db.commit()
        self.db.expire(card, ["statements"])
        return self._respond(current_user.id, card, year, month)

    def _require(self, user_id: str, card_id: str) -> Card:
        card = self.repository.get_card(user_id, card_id)
        if card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
        return card

    def _validate_category(self, user_id: str, tracks_purchases: bool, category_id: Optional[str]) -> Optional[str]:
        """A card that creates expenses when paid needs a category; one that tracks purchases does not."""
        if tracks_purchases:
            return None
        if not category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Choose an expense category for the card payments.",
            )
        category = self.expense_repository.get_category_by_id(user_id, category_id)
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense category not found.")
        return category.id

    @staticmethod
    def _to_response(
        card: Card, year: int, month: int, purchases: Optional[tuple[Decimal, int]] = None
    ) -> CardResponse:
        statement = next((s for s in card.statements if s.year == year and s.month == month), None)
        if statement is None:
            card_status = "undefined"
        elif statement.paid_on is not None:
            card_status = "paid"
        else:
            card_status = "pending"
        return CardResponse(
            id=card.id,
            name=card.name,
            last_four=card.last_four,
            payment_day=card.payment_day,
            tracks_purchases=card.tracks_purchases,
            category_id=card.category_id,
            category_name=card.category.name if card.category is not None else None,
            notes=card.notes,
            is_active=card.is_active,
            due_date=due_date_for(year, month, card.payment_day),
            status=card_status,
            statement_amount=Decimal(str(statement.amount)) if statement else None,
            paid_on=statement.paid_on if statement else None,
            purchases_total=purchases[0] if purchases else Decimal("0"),
            purchases_count=purchases[1] if purchases else 0,
        )
