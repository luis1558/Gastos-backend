from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.alerts.schemas import AlertsResponse
from app.modules.alerts.service import AlertService
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User

router = APIRouter(tags=["alerts"])


def get_alert_service(db: Session = Depends(get_db)) -> AlertService:
    return AlertService(db)


@router.get("/alerts", response_model=AlertsResponse)
def list_alerts(
    # The client sends its own local date so "today" follows the user's timezone.
    today: date = Query(...),
    days: int = Query(default=7, ge=1, le=31),
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
) -> AlertsResponse:
    return service.get_alerts(current_user, today, days)
