from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.shared.constants import (
    CounterpartyType,
    DebtStatus,
    DebtType,
    InterestType,
    RatePeriod,
    RateType,
)


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
    interest_type: InterestType = InterestType.NONE
    rate_type: RateType = RateType.FIXED
    rate_period: RatePeriod = RatePeriod.ANNUAL
    interest_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1000, decimal_places=4, max_digits=7)

    @model_validator(mode="after")
    def normalize_interest(self) -> "DebtCreateRequest":
        if self.interest_type == InterestType.NONE:
            self.rate_type = RateType.FIXED
            self.interest_rate = Decimal("0")
        return self


class DebtUpdateRequest(BaseModel):
    counterparty_id: Optional[str] = None
    due_date: Optional[date] = None
    original_amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    description: Optional[str] = Field(default=None, min_length=2, max_length=255)
    notes: Optional[str] = None
    status: Optional[DebtStatus] = None
    interest_type: Optional[InterestType] = None
    rate_type: Optional[RateType] = None
    rate_period: Optional[RatePeriod] = None
    interest_rate: Optional[Decimal] = Field(default=None, ge=0, le=1000, decimal_places=4, max_digits=7)


class DebtRateChangeCreateRequest(BaseModel):
    effective_date: date
    rate: Decimal = Field(ge=0, le=1000, decimal_places=4, max_digits=7)
    notes: Optional[str] = Field(default=None, max_length=255)


class DebtRateChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    debt_id: str
    effective_date: date
    rate: Decimal
    notes: Optional[str]
    created_at: datetime


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
    # Total still owed today: principal remaining plus accrued interest.
    remaining_amount: Decimal
    principal_remaining: Decimal
    accrued_interest: Decimal
    total_interest: Decimal
    interest_type: InterestType
    rate_type: RateType
    rate_period: RatePeriod
    interest_rate: Decimal
    current_rate: Decimal
    projected_total_at_due: Optional[Decimal] = None
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
