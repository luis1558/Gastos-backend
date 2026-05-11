from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.income.schemas import MonthlyIncomeResponse, MonthlyIncomeUpsertRequest
from app.modules.income.service import MonthlyIncomeService
from app.modules.users.models import User

router = APIRouter(prefix="/monthly-incomes", tags=["monthly-incomes"])


def get_monthly_income_service(db: Session = Depends(get_db)) -> MonthlyIncomeService:
    return MonthlyIncomeService(db)


@router.get("", response_model=list[MonthlyIncomeResponse])
def list_monthly_incomes(
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    service: MonthlyIncomeService = Depends(get_monthly_income_service),
) -> list[MonthlyIncomeResponse]:
    return service.list_by_year(current_user, year)


@router.get("/{year}/{month}", response_model=MonthlyIncomeResponse)
def get_monthly_income(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    service: MonthlyIncomeService = Depends(get_monthly_income_service),
) -> MonthlyIncomeResponse:
    return service.get(current_user, year, month)


@router.put("/{year}/{month}", response_model=MonthlyIncomeResponse)
def upsert_monthly_income(
    year: int,
    month: int,
    payload: MonthlyIncomeUpsertRequest,
    current_user: User = Depends(get_current_user),
    service: MonthlyIncomeService = Depends(get_monthly_income_service),
) -> MonthlyIncomeResponse:
    return service.upsert(
        current_user=current_user,
        year=year,
        month=month,
        base_income=payload.base_income,
        extra_income=payload.extra_income,
        notes=payload.notes,
    )
