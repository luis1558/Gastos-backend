from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_reminder_check() -> None:
    db: Session = SessionLocal()
    try:
        from app.modules.notifications.reminder_service import check_and_send_reminders

        await check_and_send_reminders(db)
    finally:
        db.close()


async def _wrapped_run() -> None:
    with suppress(Exception):
        await _run_reminder_check()


def start_scheduler() -> None:
    if settings.environment == "test":
        return

    trigger = CronTrigger(hour=8, minute=0)
    scheduler.add_job(_wrapped_run, trigger=trigger, id="debt_reminders", name="Debt reminder check")

    asyncio.create_task(_run_on_startup())
    scheduler.start()
    logger.info("Scheduler started – daily reminder check at 08:00")


async def _run_on_startup() -> None:
    await asyncio.sleep(5)
    logger.info("Running initial reminder check on startup...")
    await _wrapped_run()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
