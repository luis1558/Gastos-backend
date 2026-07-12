from __future__ import annotations

from decimal import Decimal
from typing import Optional

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
