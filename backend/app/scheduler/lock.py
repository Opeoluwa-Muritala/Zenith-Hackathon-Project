"""Database-backed, cross-worker job-run claims."""

import os
import socket
from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.clock import now_utc
from app.core.db import SessionLocal
from app.models import JobRun


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"[:64]


async def claim_job(job_name: str, scheduled_for: datetime) -> UUID | None:
    async with SessionLocal() as db:
        row = JobRun(
            job_name=job_name,
            scheduled_for=scheduled_for,
            lock_owner=worker_identity(),
            status="running",
            started_at=now_utc(),
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return None
        return row.id


async def finish_job(run_id: UUID, status: str) -> None:
    async with SessionLocal() as db:
        row = await db.get(JobRun, run_id)
        if row is not None:
            row.status = status
            row.completed_at = now_utc()
            await db.commit()


async def run_locked(
    job_name: str,
    scheduled_for: datetime,
    callback: Callable[[], Awaitable[None]],
) -> bool:
    run_id = await claim_job(job_name, scheduled_for)
    if run_id is None:
        return False
    try:
        await callback()
    except Exception:
        await finish_job(run_id, "failed")
        raise
    await finish_job(run_id, "completed")
    return True
