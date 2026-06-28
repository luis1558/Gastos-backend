from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


@router.post("/cron/check-reminders")
async def cron_check_reminders(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if settings.cron_secret and authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

    from app.modules.notifications.reminder_service import check_and_send_reminders

    try:
        await check_and_send_reminders(db)
        return {"status": "ok"}
    except Exception:
        logger.exception("Cron reminder check failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Reminder check failed")
