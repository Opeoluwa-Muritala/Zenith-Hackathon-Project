"""Durable identifier lockout with bounded exponential backoff."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.identity.audit import subject_hash
from app.ledger.service import as_utc
from app.models import AuthLockout


async def ensure_not_locked(db: AsyncSession, identifier: str) -> AuthLockout | None:
    row = await db.get(AuthLockout, subject_hash(identifier))
    locked_until = as_utc(row.locked_until) if row and row.locked_until else None
    if locked_until and locked_until > now_utc():
        retry_after = max(1, int((locked_until - now_utc()).total_seconds()))
        raise HTTPException(429, "Try again later", headers={"Retry-After": str(retry_after)})
    return row


async def register_failure(db: AsyncSession, identifier: str) -> None:
    key = subject_hash(identifier)
    query = select(AuthLockout).where(AuthLockout.identifier_hash == key).with_for_update()
    row = (await db.execute(query)).scalar_one_or_none()
    now = now_utc()
    if row is None:
        row = AuthLockout(identifier_hash=key, failed_attempts=0, locked_until=None, updated_at=now)
        db.add(row)
    row.failed_attempts += 1
    row.updated_at = now
    settings = get_settings()
    if row.failed_attempts >= settings.otp_lockout_threshold:
        exponent = row.failed_attempts - settings.otp_lockout_threshold
        seconds = min(settings.otp_lockout_base_seconds * (2**exponent), 3600)
        row.locked_until = now + timedelta(seconds=seconds)


async def clear_failures(db: AsyncSession, identifier: str) -> None:
    row = await db.get(AuthLockout, subject_hash(identifier))
    if row:
        await db.delete(row)
