"""Standalone APScheduler entrypoint; never import this from an API worker."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.clock import now_utc
from app.core.config import get_settings
from app.notifications.push import push_provider
from app.scheduler.jobs import (
    account_sync_job,
    asset_reminder_job,
    cleanup_job,
    obligation_reminder_job,
    overspending_alert_job,
    stale_marking_job,
    unlink_retry_job,
)
from app.scheduler.lock import run_locked

logger = logging.getLogger("cashlens.scheduler")


async def _run(name: str, callback: Callable[[], Awaitable[None]]) -> None:
    now = now_utc().replace(second=0, microsecond=0)
    try:
        claimed = await run_locked(name, now, callback)
        if not claimed:
            logger.info("scheduler_job_already_claimed", extra={"job_name": name})
    except Exception:
        logger.exception("scheduler_job_failed", extra={"job_name": name})


async def main() -> None:
    settings = get_settings()
    settings.validate_runtime()
    logging.basicConfig(level=logging.INFO)
    push = push_provider()
    scheduler = AsyncIOScheduler(timezone="UTC")

    def add(name: str, minutes: int, callback: Callable[[], Awaitable[None]]) -> None:
        scheduler.add_job(
            _run,
            IntervalTrigger(minutes=minutes),
            args=(name, callback),
            id=name,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=minutes * 60,
        )

    add("account_sync", 60, lambda: account_sync_job(now_utc(), push))
    add("stale_marking", 15, lambda: stale_marking_job(now_utc()))
    add("unlink_retry", 10, lambda: unlink_retry_job(now_utc()))
    add("asset_reminders", 60, lambda: asset_reminder_job(now_utc(), push))
    add("obligation_reminders", 60, lambda: obligation_reminder_job(now_utc(), push))
    add("overspending_alerts", 360, lambda: overspending_alert_job(now_utc(), push))
    add("cleanup", 60, lambda: cleanup_job(now_utc()))
    scheduler.start()
    logger.info("scheduler_started", extra={"job_count": 7})
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
