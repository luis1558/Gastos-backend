from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.cards.schemas import (
    CardCreateRequest,
    CardPayRequest,
    CardResponse,
    CardUpdateRequest,
    StatementRequest,
)
from app.modules.cards.service import CardService
from app.modules.users.models import User

router = APIRouter(tags=["cards"])


def get_card_service(db: Session = Depends(get_db)) -> CardService:
    return CardService(db)


# The client sends the month so "this month" follows the user's timezone, not the server's.
Year = Query(ge=2000, le=2100)
Month = Query(ge=1, le=12)


@router.get("/cards", response_model=list[CardResponse])
def list_cards(
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> list[CardResponse]:
    return service.list_cards(current_user, year, month)


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    payload: CardCreateRequest,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.create_card(
        current_user=current_user,
        name=payload.name,
        last_four=payload.last_four,
        payment_day=payload.payment_day,
        tracks_purchases=payload.tracks_purchases,
        category_id=payload.category_id,
        notes=payload.notes,
    )


@router.patch("/cards/{card_id}", response_model=CardResponse)
def update_card(
    card_id: str,
    payload: CardUpdateRequest,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.update_card(current_user, card_id, payload.model_dump(exclude_unset=True), year, month)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: str,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> None:
    service.delete_card(current_user, card_id)


@router.put("/cards/{card_id}/statement", response_model=CardResponse)
def set_statement(
    card_id: str,
    payload: StatementRequest,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.set_statement(current_user, card_id, year, month, payload.amount)


@router.delete("/cards/{card_id}/statement", response_model=CardResponse)
def clear_statement(
    card_id: str,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.clear_statement(current_user, card_id, year, month)


@router.post("/cards/{card_id}/payments", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def pay_card(
    card_id: str,
    payload: CardPayRequest,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.pay(
        current_user=current_user,
        card_id=card_id,
        year=payload.year,
        month=payload.month,
        amount=payload.amount,
        paid_on=payload.paid_on,
    )


@router.delete("/cards/{card_id}/payments", response_model=CardResponse)
def undo_card_payment(
    card_id: str,
    year: int = Year,
    month: int = Month,
    current_user: User = Depends(get_current_user),
    service: CardService = Depends(get_card_service),
) -> CardResponse:
    return service.undo_payment(current_user, card_id, year, month)
