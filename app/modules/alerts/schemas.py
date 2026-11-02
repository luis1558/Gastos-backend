from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


class AlertItem(BaseModel):
    # Stable key: kind + entity + due date, so the client can use it as a React key.
    id: str
    kind: Literal["debt", "fixed_payment", "card", "goal"]
    entity_id: str
    title: str
    detail: Optional[str] = None
    # Amount involved; missing when it is not known yet (a card without its statement amount).
    amount: Optional[Decimal] = None
    due_date: date
    # Negative when the due date already passed.
    days_left: int
    severity: Literal["overdue", "today", "soon"]
    # Money already set aside in an active goal linked to this item.
    saved_amount: Optional[Decimal] = None


class AlertsResponse(BaseModel):
    items: list[AlertItem]
    total: int
    overdue: int
