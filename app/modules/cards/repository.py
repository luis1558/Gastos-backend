from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.cards.models import Card, CardStatement
from app.modules.expenses.models import Expense


class CardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_cards(self, user_id: str) -> list[Card]:
        stmt = (
            select(Card)
            .options(joinedload(Card.category), joinedload(Card.statements))
            .where(Card.user_id == user_id)
            .order_by(Card.payment_day.asc(), Card.name.asc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_card(self, user_id: str, card_id: str) -> Optional[Card]:
        stmt: Select[tuple[Card]] = (
            select(Card)
            .options(joinedload(Card.category), joinedload(Card.statements))
            .where(Card.user_id == user_id, Card.id == card_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_statement(self, card_id: str, year: int, month: int) -> Optional[CardStatement]:
        stmt = select(CardStatement).where(
            CardStatement.card_id == card_id,
            CardStatement.year == year,
            CardStatement.month == month,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_card(self, card: Card) -> Card:
        self.db.add(card)
        self.db.flush()
        return card

    def delete_card(self, card: Card) -> None:
        self.db.delete(card)
        self.db.flush()

    def save_statement(self, statement: CardStatement) -> CardStatement:
        self.db.add(statement)
        self.db.flush()
        return statement

    def delete_statement(self, statement: CardStatement) -> None:
        self.db.delete(statement)
        self.db.flush()

    def purchases_summary(
        self, user_id: str, year: int, month: int, card_id: Optional[str] = None
    ) -> dict[str, tuple[Decimal, int]]:
        """Total and count of the month's purchases, per card."""
        stmt = (
            select(Expense.card_id, func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id))
            .where(
                Expense.user_id == user_id,
                Expense.card_id.is_not(None),
                Expense.year == year,
                Expense.month == month,
            )
            .group_by(Expense.card_id)
        )
        if card_id is not None:
            stmt = stmt.where(Expense.card_id == card_id)
        return {row[0]: (Decimal(str(row[1])), int(row[2])) for row in self.db.execute(stmt).all()}

    def list_purchases(self, user_id: str, card_id: str, year: int, month: int) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(joinedload(Expense.category))
            .where(
                Expense.user_id == user_id,
                Expense.card_id == card_id,
                Expense.year == year,
                Expense.month == month,
            )
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_purchases(self, user_id: str, card_id: str) -> int:
        stmt = select(func.count(Expense.id)).where(Expense.user_id == user_id, Expense.card_id == card_id)
        return int(self.db.execute(stmt).scalar_one())
