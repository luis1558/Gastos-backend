from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.fixed_payments.schemas import (
    FixedPaymentCreateRequest,
    FixedPaymentPayRequest,
    FixedPaymentResponse,
    FixedPaymentUpdateRequest,
)
from app.modules.fixed_payments.service import FixedPaymentService
from app.modules.users.models import User

router = APIRouter(tags=["fixed-payments"])


def get_fixed_payment_service(db: Session = Depends(get_db)) -> FixedPaymentService:
    return FixedPaymentService(db)


# The client sends the month so "this month" follows the user's timezone, not the server's.
Year = Query(ge=2000, le=2100)
Month = Query(ge=1, le=12)


@router.get("/fixed-payments", response_model=list[FixedPaymentResponse])
def list_fixed_payments(
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> list[FixedPaymentResponse]:
    return service.list_fixed_payments(current_user, year, month)


@router.post("/fixed-payments", response_model=FixedPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_fixed_payment(
    payload: FixedPaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> FixedPaymentResponse:
    return service.create_fixed_payment(
        current_user=current_user,
        name=payload.name,
        amount=payload.amount,
        day_of_month=payload.day_of_month,
        category_id=payload.category_id,
        notes=payload.notes,
    )


@router.patch("/fixed-payments/{fixed_payment_id}", response_model=FixedPaymentResponse)
def update_fixed_payment(
    fixed_payment_id: str,
    payload: FixedPaymentUpdateRequest,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> FixedPaymentResponse:
    return service.update_fixed_payment(
        current_user, fixed_payment_id, payload.model_dump(exclude_unset=True), year, month
    )


@router.delete("/fixed-payments/{fixed_payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fixed_payment(
    fixed_payment_id: str,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> None:
    service.delete_fixed_payment(current_user, fixed_payment_id)


@router.post("/fixed-payments/{fixed_payment_id}/payments", response_model=FixedPaymentResponse, status_code=status.HTTP_201_CREATED)
def pay_fixed_payment(
    fixed_payment_id: str,
    payload: FixedPaymentPayRequest,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> FixedPaymentResponse:
    return service.pay(
        current_user=current_user,
        fixed_payment_id=fixed_payment_id,
        year=payload.year,
        month=payload.month,
        amount=payload.amount,
        paid_on=payload.paid_on,
    )


@router.delete("/fixed-payments/{fixed_payment_id}/payments", status_code=status.HTTP_204_NO_CONTENT)
def undo_fixed_payment(
    fixed_payment_id: str,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: FixedPaymentService = Depends(get_fixed_payment_service),
) -> None:
    service.undo_payment(current_user, fixed_payment_id, year, month)
