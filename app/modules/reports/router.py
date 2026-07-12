from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.reports.schemas import MonthForecastResponse, MonthlySummaryResponse, YearlySummaryResponse
from app.modules.reports.service import ReportService
from app.modules.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db)


@router.get("/monthly-summary", response_model=MonthlySummaryResponse)
def get_monthly_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> MonthlySummaryResponse:
    return service.get_monthly_summary(current_user, year, month)


@router.get("/yearly-summary", response_model=YearlySummaryResponse)
def get_yearly_summary(
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> YearlySummaryResponse:
    return service.get_yearly_summary(current_user, year)


@router.get("/month-forecast", response_model=MonthForecastResponse)
def get_month_forecast(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> MonthForecastResponse:
    return service.get_month_forecast(current_user, year, month)
