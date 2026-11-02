from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.modules.cards.models import Card, CardStatement


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
