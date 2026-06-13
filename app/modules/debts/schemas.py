from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.constants import CounterpartyType, DebtStatus, DebtType


class CounterpartyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    type: Optional[CounterpartyType] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    notes: Optional[str] = None


class CounterpartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: Optional[CounterpartyType]
    phone: Optional[str]
    email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class DebtCreateRequest(BaseModel):
    counterparty_id: str
    type: DebtType
    origin_date: date
    due_date: Optional[date] = None
    original_amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    description: str = Field(min_length=2, max_length=255)
    notes: Optional[str] = None


class DebtUpdateRequest(BaseModel):
    counterparty_id: Optional[str] = None
    due_date: Optional[date] = None
    original_amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    description: Optional[str] = Field(default=None, min_length=2, max_length=255)
    notes: Optional[str] = None
    status: Optional[DebtStatus] = None


class DebtPaymentCreateRequest(BaseModel):
    payment_date: date
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    description: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    category_id: Optional[str] = None


class DebtPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    debt_id: str
    payment_date: date
    amount: Decimal
    description: Optional[str]
    notes: Optional[str]
    expense_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DebtResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    counterparty_id: str
    counterparty_name: str
    type: DebtType
    status: DebtStatus
    origin_date: date
    due_date: Optional[date]
    original_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    description: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]


class DebtSummaryResponse(BaseModel):
    total_receivable_pending: Decimal
    total_payable_pending: Decimal
    overdue_receivable_count: int
    overdue_payable_count: int
    active_debt_count: int
