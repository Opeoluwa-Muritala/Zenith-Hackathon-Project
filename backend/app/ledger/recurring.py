"""Rebuild account-bound recurring debit series from observed transactions."""

from collections import defaultdict
from datetime import timedelta
from statistics import median
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecurringSeries, SeriesStatus, Transaction


async def rebuild_account(db: AsyncSession, account_id: UUID, user_id: UUID, now) -> int:
    """Derive monthly series after three observations with a consistent cadence."""
    rows = (
        (
            await db.execute(
                select(Transaction)
                .where(Transaction.account_id == account_id, Transaction.merchant_id.is_not(None))
                .order_by(Transaction.posted_at)
            )
        )
        .scalars()
        .all()
    )
    groups = defaultdict(list)
    for row in rows:
        groups[(row.merchant_id, row.direction)].append(row)
    existing = {
        (s.merchant_id, s.direction): s
        for s in (
            await db.execute(
                select(RecurringSeries).where(
                    RecurringSeries.account_id == account_id, RecurringSeries.user_id == user_id
                )
            )
        ).scalars()
    }
    created = 0
    for (merchant_id, direction), items in groups.items():
        if merchant_id is None:
            continue
        if len(items) < 3:
            continue
        intervals = [
            (b.posted_at.date() - a.posted_at.date()).days
            for a, b in zip(items, items[1:], strict=False)
        ]
        valid = [day for day in intervals if 25 <= day <= 35]
        if len(valid) < 2:
            continue
        cadence = int(median(valid))
        amounts = [item.amount_minor for item in items]
        typical = int(median(amounts[:-1]))
        last = items[-1]
        missed = max(0, (now.date() - last.posted_at.date()).days // cadence)
        status = SeriesStatus.lapsed if missed >= 2 else SeriesStatus.active
        series = existing.get((merchant_id, direction))
        if series is None:
            series = RecurringSeries(
                account_id=account_id,
                user_id=user_id,
                merchant_id=merchant_id,
                cadence_days=cadence,
                typical_amount_minor=typical,
                last_amount_minor=last.amount_minor,
                previous_amount_minor=amounts[-2],
                cycles=len(items),
                first_seen_at=items[0].posted_at,
                last_seen_at=last.posted_at,
                next_expected_at=last.posted_at + timedelta(days=cadence),
                status=status,
                direction=direction,
            )
            db.add(series)
            created += 1
        else:
            series.cadence_days = cadence
            series.typical_amount_minor = typical
            series.last_amount_minor = last.amount_minor
            series.previous_amount_minor = amounts[-2]
            series.cycles = len(items)
            series.last_seen_at = last.posted_at
            series.next_expected_at = last.posted_at + timedelta(days=cadence)
            series.direction = direction
            if series.status != SeriesStatus.cancelled:
                series.status = status
    return created
