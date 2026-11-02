from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FixedPaymentCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    day_of_month: int = Field(ge=1, le=31)
    category_id: str
    notes: Optional[str] = None


class FixedPaymentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    category_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class FixedPaymentPayRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    # Defaults to the configured amount; useful when a bill varies (utilities).
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    paid_on: date


class FixedPaymentResponse(BaseModel):
    id: str
    name: str
    amount: Decimal
    day_of_month: int
    category_id: str
    category_name: str
    notes: Optional[str]
    is_active: bool
    # Due date inside the requested month (day clamped to the month's last day).
    due_date: date
    status: Literal["pending", "paid"]
    paid_amount: Optional[Decimal] = None
    paid_on: Optional[date] = None
