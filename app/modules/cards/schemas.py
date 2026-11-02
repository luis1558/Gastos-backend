from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CardCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    last_four: Optional[str] = Field(default=None, pattern=r"^\d{4}$")
    payment_day: int = Field(ge=1, le=31)
    tracks_purchases: bool = False
    category_id: Optional[str] = None
    notes: Optional[str] = None


class CardUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    # Send null explicitly to clear the digits; omit the field to keep them.
    last_four: Optional[str] = Field(default=None, pattern=r"^\d{4}$")
    payment_day: Optional[int] = Field(default=None, ge=1, le=31)
    tracks_purchases: Optional[bool] = None
    category_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class StatementRequest(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)


class CardPayRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    # Required when the month's amount has not been written down yet.
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    paid_on: date


class CardResponse(BaseModel):
    id: str
    name: str
    last_four: Optional[str]
    payment_day: int
    tracks_purchases: bool
    category_id: Optional[str]
    category_name: Optional[str]
    notes: Optional[str]
    is_active: bool
    # Due date inside the requested month (day clamped to the month's last day).
    due_date: date
    # undefined: no amount yet · pending: amount known, not paid · paid
    status: Literal["undefined", "pending", "paid"]
    statement_amount: Optional[Decimal] = None
    paid_on: Optional[date] = None
    # Purchases registered with this card in the requested month (a hint for the statement amount).
    purchases_total: Decimal = Decimal("0")
    purchases_count: int = 0


class CardPurchaseResponse(BaseModel):
    id: str
    expense_date: date
    amount: Decimal
    description: str
    category_name: str
