from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.shared.constants import GoalKind, GoalStatus


class GoalCreateRequest(BaseModel):
    kind: GoalKind
    name: str = Field(min_length=2, max_length=255)
    target_amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    target_date: Optional[date] = None
    notes: Optional[str] = None
    debt_id: Optional[str] = None
    fixed_payment_id: Optional[str] = None


class GoalUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    target_amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    # Send null explicitly to clear the date; omit the field to keep it.
    target_date: Optional[date] = None
    notes: Optional[str] = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: GoalKind
    status: GoalStatus
    name: str
    target_amount: Decimal
    target_date: Optional[date]
    notes: Optional[str]
    debt_id: Optional[str]
    debt_label: Optional[str] = None
    fixed_payment_id: Optional[str] = None
    fixed_payment_label: Optional[str] = None
    saved_amount: Decimal
    remaining_amount: Decimal
    progress_percent: Decimal
    created_at: datetime
    closed_at: Optional[datetime]


class ContributionCreateRequest(BaseModel):
    direction: Literal["deposit", "withdraw"] = "deposit"
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    contribution_date: date
    notes: Optional[str] = Field(default=None, max_length=255)


class ContributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    contribution_date: date
    # Positive when money was set aside, negative when it was taken back.
    amount: Decimal
    notes: Optional[str]
    created_at: datetime


class OpeningBalanceRequest(BaseModel):
    opening_balance: Decimal = Field(decimal_places=2, max_digits=14)


class GoalOverviewResponse(BaseModel):
    opening_balance: Decimal
    total_income: Decimal
    total_expenses: Decimal
    # opening balance + all income - all expenses
    balance: Decimal
    reserved: Decimal
    # balance - reserved: what the user can still spend
    available: Decimal
