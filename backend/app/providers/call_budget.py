"""Durable per-user provider-call accounting and refresh quotas."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.models import ProviderCallLog


async def reserve_refresh_call(
    db: AsyncSession, user_id: UUID, account_id: UUID, limit: int
) -> None:
    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    used = await db.scalar(
        select(func.count(ProviderCallLog.id)).where(
            ProviderCallLog.user_id == user_id,
            ProviderCallLog.provider == "mono",
            ProviderCallLog.operation == "balance_refresh",
            ProviderCallLog.requested_at >= month_start,
        )
    )
    if int(used or 0) >= limit:
        raise HTTPException(429, "Monthly refresh limit reached")
    db.add(
        ProviderCallLog(
            user_id=user_id,
            provider="mono",
            operation="balance_refresh",
            account_id=account_id,
            requested_at=now,
            outcome="reserved",
        )
    )
