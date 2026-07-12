from __future__ import annotations

from decimal import Decimal
from typing import Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.income.models import MonthlyIncomeConfig
from app.modules.reports.schemas import (
    CategoryExpenseSummary,
    MonthForecastResponse,
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

    def get_month_forecast(
        self,
        current_user: User,
        year: int,
        month: int,
    ) -> MonthForecastResponse:
        import calendar
        from datetime import date

        days_in_month = calendar.monthrange(year, month)[1]
        today = date.today()
        days_elapsed = today.day if (year == today.year and month == today.month) else days_in_month

        total_spent = self._as_decimal(
            self.db.execute(
                select(func.coalesce(func.sum(Expense.amount), 0)).where(
                    Expense.user_id == current_user.id,
                    Expense.year == year,
                    Expense.month == month,
                ),
            ).scalar_one(),
        )

        daily_rate = self._as_decimal(total_spent / days_elapsed) if days_elapsed else ZERO
        projected_expenses = self._as_decimal(daily_rate * days_in_month)

        income_config = self.db.execute(
            select(MonthlyIncomeConfig).where(
                MonthlyIncomeConfig.user_id == current_user.id,
                MonthlyIncomeConfig.year == year,
                MonthlyIncomeConfig.month == month,
            ),
        ).scalar_one_or_none()

        base_income = self._as_decimal(income_config.base_income if income_config else ZERO)
        extra_income = self._as_decimal(income_config.extra_income if income_config else ZERO)
        total_income = base_income + extra_income
        projected_balance = total_income - projected_expenses

        prev_year = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        prev_days_cap = min(days_elapsed, calendar.monthrange(prev_year, prev_month)[1])
        prev_cutoff = date(prev_year, prev_month, prev_days_cap)

        prev_spent = self._as_decimal(
            self.db.execute(
                select(func.coalesce(func.sum(Expense.amount), 0)).where(
                    Expense.user_id == current_user.id,
                    Expense.year == prev_year,
                    Expense.month == prev_month,
                    Expense.expense_date <= prev_cutoff,
                ),
            ).scalar_one(),
        )

        if prev_spent > ZERO:
            pace_pct = ((total_spent - prev_spent) / prev_spent * 100).quantize(Decimal("0.1"))
        else:
            pace_pct = None

        return MonthForecastResponse(
            year=year,
            month=month,
            days_in_month=days_in_month,
            days_elapsed=days_elapsed,
            total_spent=total_spent,
            daily_rate=daily_rate,
            projected_expenses=projected_expenses,
            total_income=total_income,
            projected_balance=projected_balance,
            pace_pct=pace_pct,
        )

    @staticmethod
    def _as_decimal(value: Union[Decimal, int, float]) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)).quantize(Decimal("0.01"))
