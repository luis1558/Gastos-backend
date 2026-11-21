from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Optional, Union

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.cards.models import Card, CardStatement
from app.modules.debts.models import Debt, DebtPayment
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.fixed_payments.models import FixedPayment, FixedPaymentPayment
from app.modules.income.models import MonthlyIncomeConfig
from app.modules.reports.schemas import (
    CardSpending,
    CategoryExpenseSummary,
    CategoryTrendItem,
    CategoryTrendResponse,
    MonthForecastResponse,
    MonthlySummaryResponse,
    PaymentMethodSpending,
    RecurringExpenseItem,
    RecurringExpensesResponse,
    SpendingBreakdownResponse,
    YearlySummaryResponse,
    YearMonthSummary,
)
from app.modules.users.models import User
from app.shared.constants import PaymentMethod

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


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

        balance = total_income - total_expenses
        savings_rate = (balance / total_income * 100).quantize(Decimal("0.1")) if total_income > ZERO else None
        return YearlySummaryResponse(
            year=year,
            total_income=total_income,
            total_expenses=total_expenses,
            balance=balance,
            months=months,
            savings_rate=savings_rate,
        )

    def get_month_forecast(
        self,
        current_user: User,
        year: int,
        month: int,
        today: Optional[date] = None,
    ) -> MonthForecastResponse:
        today = today or date.today()
        days_in_month = calendar.monthrange(year, month)[1]
        if (year, month) == (today.year, today.month):
            period_state = "current"
            days_elapsed = today.day
        elif (year, month) < (today.year, today.month):
            period_state = "past"
            days_elapsed = days_in_month
        else:
            period_state = "future"
            days_elapsed = 0

        expense_rows = self.db.execute(
            select(Expense.id, Expense.expense_date, Expense.amount, Expense.description).where(
                Expense.user_id == current_user.id,
                Expense.year == year,
                Expense.month == month,
            ),
        ).all()
        committed_ids = self._committed_expense_ids(current_user.id, expense_rows)
        total_spent = sum((self._as_decimal(r[2]) for r in expense_rows), ZERO)
        committed_spent = sum(
            (self._as_decimal(r[2]) for r in expense_rows if r[0] in committed_ids),
            ZERO,
        )
        variable_spent = total_spent - committed_spent

        pending_fixed_payments = ZERO
        if period_state != "past":
            pending_fixed_payments = self._pending_fixed_payments(current_user.id, year, month)

        if period_state == "past":
            # Closed month: the real totals are final, nothing is projected.
            daily_rate = (variable_spent / days_in_month).quantize(CENT)
            projected_expenses = total_spent
        elif period_state == "current":
            daily_rate = (variable_spent / days_elapsed).quantize(CENT)
            projected_variable = (variable_spent * days_in_month / days_elapsed).quantize(CENT)
            projected_expenses = projected_variable + committed_spent + pending_fixed_payments
        else:
            daily_rate = ZERO
            projected_expenses = total_spent + pending_fixed_payments

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

        pace_pct: Optional[Decimal] = None
        if period_state != "future":
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
            period_state=period_state,
            variable_spent=variable_spent,
            committed_spent=committed_spent,
            pending_fixed_payments=pending_fixed_payments,
        )

    def get_recurring_expenses(
        self,
        current_user: User,
        today: Optional[date] = None,
    ) -> RecurringExpensesResponse:
        today = today or date.today()
        periods: list[tuple[int, int]] = []
        y, m = today.year, today.month
        for _ in range(4):
            periods.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1

        rows = self.db.execute(
            select(
                Expense.description,
                Expense.category_id,
                ExpenseCategory.name,
                ExpenseCategory.slug,
                Expense.amount,
                Expense.expense_date,
                Expense.year,
                Expense.month,
                Expense.id,
            )
            .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
            .where(
                Expense.user_id == current_user.id,
                or_(
                    *[
                        and_(Expense.year == ym[0], Expense.month == ym[1])
                        for ym in periods
                    ]
                ),
            )
            .order_by(Expense.expense_date.desc())
        ).all()

        # Payments of registered fixed payments, cards and debts are already known commitments.
        committed_ids = self._committed_expense_ids(
            current_user.id,
            [(r[8], r[5], r[4], r[0]) for r in rows],
        )

        groups: dict[tuple[str, str], list] = defaultdict(list)
        for row in rows:
            if row[8] in committed_ids:
                continue
            key = (row[0].strip().lower(), row[1])
            groups[key].append(row)

        items: list[RecurringExpenseItem] = []
        for (norm_desc, cat_id), group_rows in groups.items():
            months_seen = {(r[6], r[7]) for r in group_rows}
            if len(months_seen) < 3:
                continue
            amounts = [self._as_decimal(r[4]) for r in group_rows]
            avg_amount = sum(amounts) / len(amounts)
            latest = group_rows[0]
            items.append(
                RecurringExpenseItem(
                    description=latest[0],
                    category_id=cat_id,
                    category_name=latest[2],
                    category_slug=latest[3],
                    avg_amount=avg_amount.quantize(Decimal("0.01")),
                    occurrence_months=len(months_seen),
                    last_amount=self._as_decimal(latest[4]),
                    last_date=latest[5],
                )
            )

        items.sort(key=lambda x: x.avg_amount, reverse=True)
        return RecurringExpensesResponse(checked_months=4, items=items)

    def get_category_trend(self, current_user: User, year: int) -> CategoryTrendResponse:
        rows = self.db.execute(
            select(
                Expense.category_id,
                ExpenseCategory.name,
                Expense.month,
                func.coalesce(func.sum(Expense.amount), 0),
            )
            .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
            .where(Expense.user_id == current_user.id, Expense.year == year)
            .group_by(Expense.category_id, ExpenseCategory.name, Expense.month),
        ).all()

        names: dict[str, str] = {}
        monthly: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO] * 12)
        for category_id, name, month, amount in rows:
            names[category_id] = name
            monthly[category_id][int(month) - 1] = self._as_decimal(amount)

        ranked = sorted(names, key=lambda cid: (-sum(monthly[cid], ZERO), names[cid]))[:5]
        return CategoryTrendResponse(
            year=year,
            categories=[
                CategoryTrendItem(category_id=cid, category_name=names[cid], monthly=monthly[cid])
                for cid in ranked
            ],
        )

    def get_spending_breakdown(self, current_user: User, year: int, month: int) -> SpendingBreakdownResponse:
        period = (
            Expense.user_id == current_user.id,
            Expense.year == year,
            Expense.month == month,
        )
        method_rows = self.db.execute(
            select(
                Expense.payment_method,
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            )
            .where(*period)
            .group_by(Expense.payment_method),
        ).all()
        card_rows = self.db.execute(
            select(
                Card.id,
                Card.name,
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            )
            .join(Card, Expense.card_id == Card.id)
            .where(*period)
            .group_by(Card.id, Card.name),
        ).all()

        by_payment_method = [
            PaymentMethodSpending(
                payment_method=method.value if isinstance(method, PaymentMethod) else method,
                amount=self._as_decimal(amount),
                count=int(count),
            )
            for method, amount, count in method_rows
        ]
        by_payment_method.sort(key=lambda x: (-x.amount, x.payment_method or ""))
        by_card = [
            CardSpending(card_id=card_id, card_name=name, amount=self._as_decimal(amount), count=int(count))
            for card_id, name, amount, count in card_rows
        ]
        by_card.sort(key=lambda x: (-x.amount, x.card_name))
        return SpendingBreakdownResponse(by_payment_method=by_payment_method, by_card=by_card)

    def _committed_expense_ids(self, user_id: str, expense_rows: Iterable) -> set[str]:
        """Ids of expenses created by paying a fixed payment, a card statement or a debt.

        `expense_rows` are (id, expense_date, amount, description) tuples.
        """
        rows = list(expense_rows)
        if not rows:
            return set()
        linked = set(
            self.db.execute(
                select(FixedPaymentPayment.expense_id).where(
                    FixedPaymentPayment.user_id == user_id,
                    FixedPaymentPayment.expense_id.is_not(None),
                ),
            ).scalars()
        )
        linked |= set(
            self.db.execute(
                select(CardStatement.expense_id).where(
                    CardStatement.user_id == user_id,
                    CardStatement.expense_id.is_not(None),
                ),
            ).scalars()
        )
        # Debt payments do not store the expense id; the expense is created with the
        # payment's date, amount and description (or "Pago de deuda: <debt>").
        debt_keys = {
            (payment_date, self._as_decimal(amount).quantize(CENT), description or f"Pago de deuda: {debt_description}")
            for payment_date, amount, description, debt_description in self.db.execute(
                select(DebtPayment.payment_date, DebtPayment.amount, DebtPayment.description, Debt.description)
                .join(Debt, DebtPayment.debt_id == Debt.id)
                .where(DebtPayment.user_id == user_id),
            ).all()
        }
        committed: set[str] = set()
        for expense_id, expense_date, amount, description in rows:
            if expense_id in linked or (
                (expense_date, self._as_decimal(amount).quantize(CENT), description) in debt_keys
            ):
                committed.add(expense_id)
        return committed

    def _pending_fixed_payments(self, user_id: str, year: int, month: int) -> Decimal:
        paid_ids = select(FixedPaymentPayment.fixed_payment_id).where(
            FixedPaymentPayment.user_id == user_id,
            FixedPaymentPayment.year == year,
            FixedPaymentPayment.month == month,
        )
        return self._as_decimal(
            self.db.execute(
                select(func.coalesce(func.sum(FixedPayment.amount), 0)).where(
                    FixedPayment.user_id == user_id,
                    FixedPayment.is_active.is_(True),
                    FixedPayment.id.not_in(paid_ids),
                ),
            ).scalar_one(),
        )

    @staticmethod
    def _as_decimal(value: Union[Decimal, int, float]) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)).quantize(Decimal("0.01"))
