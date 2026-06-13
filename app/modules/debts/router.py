from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.debts.schemas import (
    CounterpartyCreateRequest,
    CounterpartyResponse,
    DebtCreateRequest,
    DebtPaymentCreateRequest,
    DebtPaymentResponse,
    DebtResponse,
    DebtSummaryResponse,
    DebtUpdateRequest,
)
from app.modules.debts.service import DebtService
from app.modules.users.models import User
from app.shared.constants import DebtStatus, DebtType

router = APIRouter(tags=["debts"])


def get_debt_service(db: Session = Depends(get_db)) -> DebtService:
    return DebtService(db)


@router.get("/counterparties", response_model=list[CounterpartyResponse])
def list_counterparties(
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> list[CounterpartyResponse]:
    return service.list_counterparties(current_user)


@router.post("/counterparties", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
def create_counterparty(
    payload: CounterpartyCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> CounterpartyResponse:
    return service.create_counterparty(
        current_user=current_user,
        name=payload.name,
        counterparty_type=payload.type,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
    )


@router.get("/debts", response_model=list[DebtResponse])
def list_debts(
    type: Optional[DebtType] = Query(default=None),
    status_filter: Optional[DebtStatus] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> list[DebtResponse]:
    return service.list_debts(current_user, type, status_filter)


@router.post("/debts", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
def create_debt(
    payload: DebtCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> DebtResponse:
    return service.create_debt(
        current_user=current_user,
        counterparty_id=payload.counterparty_id,
        debt_type=payload.type,
        origin_date=payload.origin_date,
        due_date=payload.due_date,
        original_amount=payload.original_amount,
        description=payload.description,
        notes=payload.notes,
    )


@router.get("/debts/summary", response_model=DebtSummaryResponse)
def get_debt_summary(
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> DebtSummaryResponse:
    return service.get_summary(current_user)


@router.get("/debts/{debt_id}", response_model=DebtResponse)
def get_debt(
    debt_id: str,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> DebtResponse:
    return service.get_debt(current_user, debt_id)


@router.patch("/debts/{debt_id}", response_model=DebtResponse)
def update_debt(
    debt_id: str,
    payload: DebtUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> DebtResponse:
    return service.update_debt(
        current_user=current_user,
        debt_id=debt_id,
        counterparty_id=payload.counterparty_id,
        due_date=payload.due_date,
        original_amount=payload.original_amount,
        description=payload.description,
        notes=payload.notes,
        requested_status=payload.status,
    )


@router.get("/debts/{debt_id}/payments", response_model=list[DebtPaymentResponse])
def list_debt_payments(
    debt_id: str,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> list[DebtPaymentResponse]:
    return service.list_payments(current_user, debt_id)


@router.post("/debts/{debt_id}/payments", response_model=DebtPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_debt_payment(
    debt_id: str,
    payload: DebtPaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DebtService = Depends(get_debt_service),
) -> DebtPaymentResponse:
    return service.create_payment(
        current_user=current_user,
        debt_id=debt_id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        description=payload.description,
        notes=payload.notes,
        category_id=payload.category_id,
    )
