"""Non-destructive Phase 9 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.core.encryption import encrypt_field, hash_field
from app.models import PendingUnlink, WipeAudit


async def check() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0024":
            raise RuntimeError(f"Expected revision 0024, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            sample_identifier = f"phase9-provider-{uuid4().hex}"
            db.add_all(
                (
                    PendingUnlink(
                        user_hash=uuid4().hex * 2,
                        provider="mono",
                        provider_account_id_encrypted=encrypt_field(sample_identifier),
                        provider_account_id_hash=hash_field(sample_identifier),
                        attempts=0,
                        created_at=now,
                    ),
                    WipeAudit(user_hash=uuid4().hex * 2, wiped_at=now),
                )
            )
            await db.flush()
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 9 PostgreSQL check passed at revision 0024; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
