"""Per-user/global daily token budgets and a process-local chat rate guard."""

from collections import defaultdict, deque
from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AiAudit

_requests: dict[UUID, deque[datetime]] = defaultdict(deque)


def chat_rate_allowed(user_id: UUID, now: datetime | None = None) -> bool:
    """Allow a bounded number of chat calls per user in one process."""
    config = get_settings()
    moment = now or datetime.now(UTC)
    recent = _requests[user_id]
    while recent and (moment - recent[0]).total_seconds() >= 60:
        recent.popleft()
    if len(recent) >= config.ai_chat_requests_per_minute:
        return False
    recent.append(moment)
    return True


async def budget_allowed(db: AsyncSession, user_id: UUID, now: datetime) -> bool:
    """Check audited token use since UTC midnight against both circuit breakers."""
    config = get_settings()
    start = datetime.combine(now.astimezone(UTC).date(), time.min, UTC)
    user_total = await db.scalar(
        select(func.coalesce(func.sum(AiAudit.input_tokens + AiAudit.output_tokens), 0)).where(
            AiAudit.user_id == user_id, AiAudit.created_at >= start
        )
    )
    global_total = await db.scalar(
        select(func.coalesce(func.sum(AiAudit.input_tokens + AiAudit.output_tokens), 0)).where(
            AiAudit.created_at >= start
        )
    )
    return (
        int(user_total or 0) < config.ai_daily_token_budget_per_user
        and int(global_total or 0) < config.ai_global_daily_token_budget
    )


def local_midnight(now: datetime) -> datetime:
    """Return start of current UTC day for audit queries."""
    return datetime.combine(now.astimezone(UTC).date(), time.min, UTC)
