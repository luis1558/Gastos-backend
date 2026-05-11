from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MonthlyIncomeUpsertRequest(BaseModel):
    base_income: Decimal = Field(ge=0, decimal_places=2, max_digits=14)
    extra_income: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2, max_digits=14)
    notes: Optional[str] = None


class MonthlyIncomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    year: int
    month: int
    base_income: Decimal
    extra_income: Decimal
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
