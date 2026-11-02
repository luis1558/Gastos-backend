from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.cards.models import Card
from app.modules.cards.repository import CardRepository
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.repository import ExpenseRepository
from app.modules.expenses.schemas import (
    ExpenseCategoryResponse,
    ExpenseListItemResponse,
    ExpenseResponse,
)
from app.modules.users.models import User
from app.shared.constants import PaymentMethod


class ExpenseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ExpenseRepository(db)
        self.card_repository = CardRepository(db)

    def create_category(
        self,
        current_user: User,
        name: str,
        slug: str,
        color: Optional[str],
        icon: Optional[str],
    ) -> ExpenseCategoryResponse:
        normalized_slug = slug.strip().lower()
        existing = self.repository.get_category_by_slug(current_user.id, normalized_slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with that slug already exists.",
            )
        category = ExpenseCategory(
            user_id=current_user.id,
            name=name.strip(),
            slug=normalized_slug,
            color=color,
            icon=icon,
        )
        self.repository.save_category(category)
        self.db.commit()
        self.db.refresh(category)
        return ExpenseCategoryResponse.model_validate(category)

    def update_category(
        self,
        current_user: User,
        category_id: str,
        name: Optional[str],
        color: Optional[str],
        icon: Optional[str],
        is_active: Optional[bool],
    ) -> ExpenseCategoryResponse:
        category = self.repository.get_category_by_id(current_user.id, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found.",
            )
        if name is not None:
            category.name = name.strip()
        if color is not None:
            category.color = color
        if icon is not None:
            category.icon = icon
        if is_active is not None:
            category.is_active = is_active
        self.repository.save_category(category)
        self.db.commit()
        self.db.refresh(category)
        return ExpenseCategoryResponse.model_validate(category)

    def list_categories(
        self,
        current_user: User,
        active_only: Optional[bool],
    ) -> list[ExpenseCategoryResponse]:
        categories = self.repository.list_categories(current_user.id, active_only)
        return [ExpenseCategoryResponse.model_validate(category) for category in categories]

    def create_expense(
        self,
        current_user: User,
        category_id: str,
        expense_date: date,
        amount: Decimal,
        description: str,
        payment_method: Optional[PaymentMethod],
        notes: Optional[str],
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
        card_id: Optional[str] = None,
    ) -> ExpenseResponse:
        category = self._require_category(current_user.id, category_id)
        if card_id is not None:
            card_id = self._require_card(current_user.id, card_id, payment_method).id
            payment_method = PaymentMethod.CREDIT_CARD
        expense = Expense(
            user_id=current_user.id,
            category_id=category.id,
            expense_date=expense_date,
            year=period_year if period_year is not None else expense_date.year,
            month=period_month if period_month is not None else expense_date.month,
            amount=amount,
            description=description,
            payment_method=payment_method,
            notes=notes,
            card_id=card_id,
        )
        self.repository.save_expense(expense)
        self.db.commit()
        self.db.refresh(expense)
        return ExpenseResponse.model_validate(expense)

    def update_expense(
        self,
        current_user: User,
        expense_id: str,
        category_id: Optional[str],
        expense_date: Optional[date],
        amount: Optional[Decimal],
        description: Optional[str],
        payment_method: Optional[PaymentMethod],
        notes: Optional[str],
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
        card_id: Optional[str] = None,
        card_id_provided: bool = False,
    ) -> ExpenseResponse:
        expense = self.repository.get_expense(current_user.id, expense_id)
        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )
        if category_id is not None:
            category = self._require_category(current_user.id, category_id)
            expense.category_id = category.id
        if expense_date is not None:
            expense.expense_date = expense_date
            # Only sync period from date if no explicit period was provided
            if period_year is None:
                expense.year = expense_date.year
            if period_month is None:
                expense.month = expense_date.month
        if period_year is not None:
            expense.year = period_year
        if period_month is not None:
            expense.month = period_month
        if amount is not None:
            expense.amount = amount
        if description is not None:
            expense.description = description
        if payment_method is not None:
            expense.payment_method = payment_method
            # Only credit card purchases can belong to a card.
            if payment_method != PaymentMethod.CREDIT_CARD and not card_id_provided:
                expense.card_id = None
        if card_id_provided:
            if card_id is None:
                expense.card_id = None
            else:
                expense.card_id = self._require_card(current_user.id, card_id, payment_method).id
                expense.payment_method = PaymentMethod.CREDIT_CARD
        if notes is not None:
            expense.notes = notes
        self.repository.save_expense(expense)
        self.db.commit()
        self.db.refresh(expense)
        return ExpenseResponse.model_validate(expense)

    def list_expenses(
        self,
        current_user: User,
        year: int,
        month: Optional[int],
    ) -> list[ExpenseListItemResponse]:
        expenses = self.repository.list_expenses(current_user.id, year, month)
        items: list[ExpenseListItemResponse] = []
        for expense in expenses:
            items.append(
                ExpenseListItemResponse(
                    id=expense.id,
                    category_id=expense.category_id,
                    expense_date=expense.expense_date,
                    year=expense.year,
                    month=expense.month,
                    amount=expense.amount,
                    description=expense.description,
                    payment_method=expense.payment_method,
                    notes=expense.notes,
                    created_at=expense.created_at,
                    updated_at=expense.updated_at,
                    category_name=expense.category.name,
                    category_slug=expense.category.slug,
                    card_id=expense.card_id,
                    card_name=expense.card.name if expense.card is not None else None,
                ),
            )
        return items

    def delete_expense(self, current_user: User, expense_id: str) -> None:
        expense = self.repository.get_expense(current_user.id, expense_id)
        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )
        self.repository.delete_expense(expense)
        self.db.commit()

    def _require_card(
        self, user_id: str, card_id: str, payment_method: Optional[PaymentMethod]
    ) -> Card:
        """A purchase can only be linked to an active card that tracks its purchases."""
        card = self.card_repository.get_card(user_id, card_id)
        if card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
        if not card.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This card is inactive.")
        if not card.tracks_purchases:
            # Paying that card creates an expense, so tracking purchases too would count them twice.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This card only tracks its payment. Switch it to tracking purchases first.",
            )
        if payment_method is not None and payment_method != PaymentMethod.CREDIT_CARD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A card purchase must use credit card as the payment method.",
            )
        return card

    def _require_category(self, user_id: str, category_id: str) -> ExpenseCategory:
        category = self.repository.get_category_by_id(user_id, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found.",
            )
        if not category.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense category is inactive.",
            )
        return category
