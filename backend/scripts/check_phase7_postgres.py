"""Non-destructive Phase 7 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models import BookkeeperInvite, ReportShareLink, User


async def check() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0022":
            raise RuntimeError(f"Expected revision 0022, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            owner = User(email=f"owner-{uuid4().hex[:8]}@example.test", created_at=now)
            db.add(owner)
            await db.flush()
            db.add_all(
                (
                    ReportShareLink(
                        user_id=owner.id,
                        month=date(now.year, now.month, 1),
                        token_hash=uuid4().hex * 2,
                        created_at=now,
                        expires_at=now + timedelta(minutes=5),
                    ),
                    BookkeeperInvite(
                        owner_user_id=owner.id,
                        email="bookkeeper@example.test",
                        token_hash=uuid4().hex * 2,
                        status="pending",
                        created_at=now,
                        expires_at=now + timedelta(minutes=5),
                    ),
                )
            )
            await db.flush()
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 7 PostgreSQL check passed at revision 0022; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
