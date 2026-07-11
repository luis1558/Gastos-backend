from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.shared.constants import PaymentMethod


class ExpenseCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    color: Optional[str] = Field(default=None, max_length=32)
    icon: Optional[str] = Field(default=None, max_length=64)


class ExpenseCategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    color: Optional[str] = Field(default=None, max_length=32)
    icon: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None


class ExpenseCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    color: Optional[str]
    icon: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExpenseCreateRequest(BaseModel):
    category_id: str
    expense_date: date
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    description: str = Field(min_length=2, max_length=255)
    payment_method: Optional[PaymentMethod] = None
    notes: Optional[str] = None
    # Billing period — defaults to expense_date's month/year if not provided.
    # Use this when the expense happened in one month but belongs to another period.
    period_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    period_month: Optional[int] = Field(default=None, ge=1, le=12)


class ExpenseUpdateRequest(BaseModel):
    category_id: Optional[str] = None
    expense_date: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    description: Optional[str] = Field(default=None, min_length=2, max_length=255)
    payment_method: Optional[PaymentMethod] = None
    notes: Optional[str] = None
    period_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    period_month: Optional[int] = Field(default=None, ge=1, le=12)


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str
    expense_date: date
    year: int
    month: int
    amount: Decimal
    description: str
    payment_method: Optional[PaymentMethod]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ExpenseListItemResponse(ExpenseResponse):
    category_name: str
    category_slug: str
