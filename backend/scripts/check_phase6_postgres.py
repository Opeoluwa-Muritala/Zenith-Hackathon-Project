"""Non-destructive Phase 6 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models import User, UserSettings


async def check() -> None:
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0021":
            raise RuntimeError(f"Expected revision 0021, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            user = User(created_at=datetime.now(UTC))
            db.add(user)
            await db.flush()
            preference = UserSettings(user_id=user.id, privacy_blur=True)
            db.add(preference)
            await db.flush()
            await db.refresh(preference)
            if preference.privacy_blur is not True:
                raise RuntimeError("Privacy preference did not round-trip")
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 6 PostgreSQL check passed at revision 0021; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
