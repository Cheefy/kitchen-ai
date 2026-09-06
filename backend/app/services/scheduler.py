"""Weigh-in reminder (kitchen_ai_spec.md §7/§10). notify() already existed
but nothing ever called it on a schedule -- this is that trigger. Checks
once daily whether the last weigh-in is 2+ days old (or none exist at
all) and sends a Pushover nudge if so; stops firing again as soon as a
new one is logged, until 2 days pass again.
"""

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session
from app.models import WeighIn
from app.services.notifications import notify

logger = logging.getLogger(__name__)

WEIGH_IN_REMINDER_DAYS = 2

scheduler = AsyncIOScheduler()


async def check_weigh_in_reminder() -> None:
    async with async_session() as session:
        latest = await session.scalar(select(WeighIn).order_by(WeighIn.date.desc()).limit(1))
        if latest is not None and (date.today() - latest.date).days < WEIGH_IN_REMINDER_DAYS:
            return
        logger.info(
            "Sending weigh-in reminder (last weigh-in: %s)", latest.date if latest else "never"
        )
        await notify(
            "No weigh-in logged in a couple days -- got a number for me?",
            title="Kitchen AI",
        )


def start_scheduler() -> None:
    scheduler.add_job(
        check_weigh_in_reminder, "cron", hour=9, id="weigh_in_reminder", replace_existing=True
    )
    scheduler.start()


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
