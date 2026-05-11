from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.modules.expenses.models import Expense, ExpenseCategory


class ExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_category_by_slug(self, user_id: str, slug: str) -> Optional[ExpenseCategory]:
        stmt: Select[tuple[ExpenseCategory]] = select(ExpenseCategory).where(
            ExpenseCategory.user_id == user_id,
            ExpenseCategory.slug == slug,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_category_by_id(self, user_id: str, category_id: str) -> Optional[ExpenseCategory]:
        stmt: Select[tuple[ExpenseCategory]] = select(ExpenseCategory).where(
            ExpenseCategory.user_id == user_id,
            ExpenseCategory.id == category_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_categories(
        self,
        user_id: str,
        active_only: Optional[bool] = None,
    ) -> list[ExpenseCategory]:
        stmt = select(ExpenseCategory).where(ExpenseCategory.user_id == user_id)
        if active_only is True:
            stmt = stmt.where(ExpenseCategory.is_active.is_(True))
        stmt = stmt.order_by(ExpenseCategory.name.asc())
        return list(self.db.execute(stmt).scalars().all())

    def save_category(self, category: ExpenseCategory) -> ExpenseCategory:
        self.db.add(category)
        self.db.flush()
        return category

    def get_expense(self, user_id: str, expense_id: str) -> Optional[Expense]:
        stmt: Select[tuple[Expense]] = (
            select(Expense)
            .options(joinedload(Expense.category))
            .where(Expense.user_id == user_id, Expense.id == expense_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_expenses(
        self,
        user_id: str,
        year: int,
        month: Optional[int] = None,
    ) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(joinedload(Expense.category))
            .where(Expense.user_id == user_id, Expense.year == year)
        )
        if month is not None:
            stmt = stmt.where(Expense.month == month)
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def save_expense(self, expense: Expense) -> Expense:
        self.db.add(expense)
        self.db.flush()
        return expense

    def delete_expense(self, expense: Expense) -> None:
        self.db.delete(expense)
