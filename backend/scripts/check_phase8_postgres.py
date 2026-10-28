"""Non-destructive Phase 8 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.core.encryption import encrypt_field, hash_field
from app.models import DeviceToken, JobRun, NotificationLog, User


async def check() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0023":
            raise RuntimeError(f"Expected revision 0023, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            user = User(email=f"phase8-{uuid4().hex[:8]}@example.test", created_at=now)
            db.add(user)
            await db.flush()
            sample_device_value = f"phase8-device-{uuid4().hex}"
            device = DeviceToken(
                user_id=user.id,
                token_encrypted=encrypt_field(sample_device_value),
                token_hash=hash_field(sample_device_value),
                platform="android",
                last_seen_at=now,
            )
            db.add(device)
            await db.flush()
            db.add_all(
                (
                    NotificationLog(
                        user_id=user.id,
                        device_id=device.id,
                        event_key=f"smoke:{uuid4().hex}",
                        kind="smoke",
                        status="sent",
                        attempts=1,
                        last_attempt_at=now,
                        sent_at=now,
                    ),
                    JobRun(
                        job_name="phase8_smoke",
                        scheduled_for=now,
                        lock_owner="verification",
                        status="completed",
                        started_at=now,
                        completed_at=now,
                    ),
                )
            )
            await db.flush()
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 8 PostgreSQL check passed at revision 0023; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
