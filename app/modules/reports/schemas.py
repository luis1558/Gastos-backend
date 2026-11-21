from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class CategoryExpenseSummary(BaseModel):
    category_id: str
    category_name: str
    category_slug: str
    total_amount: Decimal
    transaction_count: int


class MonthlySummaryResponse(BaseModel):
    year: int
    month: int
    base_income: Decimal
    extra_income: Decimal
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    transaction_count: int
    top_categories: list[CategoryExpenseSummary]


class YearMonthSummary(BaseModel):
    year: int
    month: int
    base_income: Decimal
    extra_income: Decimal
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    transaction_count: int


class YearlySummaryResponse(BaseModel):
    year: int
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    months: list[YearMonthSummary]
    # Yearly balance / yearly income * 100 (weighted); None when there is no income.
    savings_rate: Optional[Decimal] = None


class MonthForecastResponse(BaseModel):
    year: int
    month: int
    days_in_month: int
    days_elapsed: int
    total_spent: Decimal
    daily_rate: Decimal
    projected_expenses: Decimal
    total_income: Decimal
    projected_balance: Decimal
    pace_pct: Optional[Decimal]
    # "past": closed month (real totals), "current": in progress, "future": not started.
    period_state: Literal["past", "current", "future"]
    # Spending that is projected linearly (not fixed / card / debt payments).
    variable_spent: Decimal
    # Fixed, card statement and debt payments already recorded; added as-is.
    committed_spent: Decimal
    # Active fixed payments not yet paid this month (0 for past months).
    pending_fixed_payments: Decimal


class RecurringExpenseItem(BaseModel):
    description: str
    category_id: str
    category_name: str
    category_slug: str
    avg_amount: Decimal
    occurrence_months: int
    last_amount: Decimal
    last_date: date


class RecurringExpensesResponse(BaseModel):
    checked_months: int
    items: list[RecurringExpenseItem]


class CategoryTrendItem(BaseModel):
    category_id: Optional[str]
    category_name: str
    monthly: list[Decimal]


class CategoryTrendResponse(BaseModel):
    year: int
    categories: list[CategoryTrendItem]


class PaymentMethodSpending(BaseModel):
    payment_method: Optional[str]
    amount: Decimal
    count: int


class CardSpending(BaseModel):
    card_id: str
    card_name: str
    amount: Decimal
    count: int


class SpendingBreakdownResponse(BaseModel):
    by_payment_method: list[PaymentMethodSpending]
    by_card: list[CardSpending]
