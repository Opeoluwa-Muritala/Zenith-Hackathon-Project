"""Server-side free trial and paid SME entitlement checks."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ledger.service import as_utc
from app.models import ProviderLink, UserPlan


async def plan_for(db: AsyncSession, user_id: UUID, now: datetime) -> UserPlan:
    row = await db.get(UserPlan, user_id)
    if row is None:
        row = UserPlan(user_id=user_id, paid_sme=False, updated_at=now)
        db.add(row)
        await db.flush()
    return row


async def require_live_sync(
    db: AsyncSession,
    user_id: UUID,
    now: datetime,
    *,
    new_account: bool = False,
) -> UserPlan:
    plan = await plan_for(db, user_id, now)
    if plan.paid_sme:
        return plan
    settings = get_settings()
    if new_account:
        active_links = int(
            await db.scalar(
                select(func.count()).where(
                    ProviderLink.user_id == user_id,
                    ProviderLink.status.notin_(("unlinked", "pending_unlink")),
                )
            )
            or 0
        )
        if active_links >= settings.free_live_account_limit:
            raise HTTPException(402, "Free live-account limit reached")
    if plan.trial_started_at is None:
        plan.trial_started_at = now
        plan.trial_ends_at = now + timedelta(days=settings.live_sync_trial_days)
        plan.updated_at = now
        await db.flush()
    trial_end = as_utc(plan.trial_ends_at)
    if trial_end is None or now >= trial_end:
        raise HTTPException(402, "Live-sync trial has ended")
    return plan


def trial_status(plan: UserPlan, now: datetime) -> str:
    if plan.paid_sme:
        return "paid"
    if plan.trial_started_at is None:
        return "not_started"
    trial_end = as_utc(plan.trial_ends_at)
    return "active" if trial_end and now < trial_end else "expired"
