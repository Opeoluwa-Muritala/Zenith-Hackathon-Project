"""Non-destructive Phase 10 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models import UpgradeTapEvent, User, UserPlan


async def check() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0025":
            raise RuntimeError(f"Expected revision 0025, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            user = User(email=f"phase10-{uuid4().hex[:8]}@example.test", created_at=now)
            db.add(user)
            await db.flush()
            db.add_all(
                (
                    UserPlan(
                        user_id=user.id,
                        paid_sme=False,
                        trial_started_at=now,
                        trial_ends_at=now + timedelta(days=14),
                        updated_at=now,
                    ),
                    UpgradeTapEvent(
                        user_id=user.id,
                        surface="report",
                        desired_tier="sme",
                        occurred_at=now,
                    ),
                )
            )
            await db.flush()
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 10 PostgreSQL check passed at revision 0025; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
