from __future__ import annotations

from decimal import Decimal
from typing import Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.income.models import MonthlyIncomeConfig
from app.modules.reports.schemas import (
    CategoryExpenseSummary,
    MonthlySummaryResponse,
    YearlySummaryResponse,
    YearMonthSummary,
)
from app.modules.users.models import User

ZERO = Decimal("0.00")


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_monthly_summary(
        self,
        current_user: User,
        year: int,
        month: int,
    ) -> MonthlySummaryResponse:
        income_config = self.db.execute(
            select(MonthlyIncomeConfig).where(
                MonthlyIncomeConfig.user_id == current_user.id,
                MonthlyIncomeConfig.year == year,
                MonthlyIncomeConfig.month == month,
            ),
        ).scalar_one_or_none()

        expense_totals = self.db.execute(
            select(
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            ).where(
                Expense.user_id == current_user.id,
                Expense.year == year,
                Expense.month == month,
            ),
        ).one()

        category_rows = self.db.execute(
            select(
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.slug,
                func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
                func.count(Expense.id).label("transaction_count"),
            )
            .join(Expense, Expense.category_id == ExpenseCategory.id)
            .where(
                Expense.user_id == current_user.id,
                Expense.year == year,
                Expense.month == month,
            )
            .group_by(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.slug)
            .order_by(func.sum(Expense.amount).desc(), ExpenseCategory.name.asc()),
        ).all()

        base_income = self._as_decimal(income_config.base_income if income_config else ZERO)
        extra_income = self._as_decimal(income_config.extra_income if income_config else ZERO)
        total_expenses = self._as_decimal(expense_totals[0])
        total_income = base_income + extra_income

        return MonthlySummaryResponse(
            year=year,
            month=month,
            base_income=base_income,
            extra_income=extra_income,
            total_income=total_income,
            total_expenses=total_expenses,
            balance=total_income - total_expenses,
            transaction_count=int(expense_totals[1] or 0),
            top_categories=[
                CategoryExpenseSummary(
                    category_id=row[0],
                    category_name=row[1],
                    category_slug=row[2],
                    total_amount=self._as_decimal(row[3]),
                    transaction_count=int(row[4]),
                )
                for row in category_rows
            ],
        )

    def get_yearly_summary(
        self,
        current_user: User,
        year: int,
    ) -> YearlySummaryResponse:
        income_rows = self.db.execute(
            select(
                MonthlyIncomeConfig.month,
                MonthlyIncomeConfig.base_income,
                MonthlyIncomeConfig.extra_income,
            ).where(
                MonthlyIncomeConfig.user_id == current_user.id,
                MonthlyIncomeConfig.year == year,
            ),
        ).all()
        income_by_month = {
            row[0]: {
                "base_income": self._as_decimal(row[1]),
                "extra_income": self._as_decimal(row[2]),
            }
            for row in income_rows
        }

        expense_rows = self.db.execute(
            select(
                Expense.month,
                func.coalesce(func.sum(Expense.amount), 0).label("total_expenses"),
                func.count(Expense.id).label("transaction_count"),
            )
            .where(
                Expense.user_id == current_user.id,
                Expense.year == year,
            )
            .group_by(Expense.month),
        ).all()
        expense_by_month = {
            row[0]: {
                "total_expenses": self._as_decimal(row[1]),
                "transaction_count": int(row[2]),
            }
            for row in expense_rows
        }

        months: list[YearMonthSummary] = []
        total_income = ZERO
        total_expenses = ZERO

        for month in range(1, 13):
            income_data = income_by_month.get(month, {})
            expense_data = expense_by_month.get(month, {})
            base_income = self._as_decimal(income_data.get("base_income", ZERO))
            extra_income = self._as_decimal(income_data.get("extra_income", ZERO))
            monthly_income = base_income + extra_income
            monthly_expenses = self._as_decimal(expense_data.get("total_expenses", ZERO))
            transaction_count = int(expense_data.get("transaction_count", 0))
            balance = monthly_income - monthly_expenses

            total_income += monthly_income
            total_expenses += monthly_expenses

            months.append(
                YearMonthSummary(
                    year=year,
                    month=month,
                    base_income=base_income,
                    extra_income=extra_income,
                    total_income=monthly_income,
                    total_expenses=monthly_expenses,
                    balance=balance,
                    transaction_count=transaction_count,
                ),
            )

        return YearlySummaryResponse(
            year=year,
            total_income=total_income,
            total_expenses=total_expenses,
            balance=total_income - total_expenses,
            months=months,
        )

    @staticmethod
    def _as_decimal(value: Union[Decimal, int, float]) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)).quantize(Decimal("0.01"))
