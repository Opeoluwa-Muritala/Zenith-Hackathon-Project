"""Non-destructive Phase 4 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from app.core.db import engine


async def check() -> None:
    expected = {
        "classification_corrections",
        "reviewed_global_rules",
        "transfer_suggestions",
    }
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0019":
            raise RuntimeError(f"Expected revision 0019, found {revision!r}")
        rows = await connection.execute(
            text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = current_schema()")
        )
        present = {row[0] for row in rows}
        missing = expected - present
        if missing:
            raise RuntimeError(f"Missing Phase 4 tables: {sorted(missing)}")

        await connection.rollback()
        transaction = await connection.begin()
        try:
            user_id, suggestion_id, rule_id, correction_id = (uuid4() for _ in range(4))
            now = datetime.now(UTC)
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, :created_at)"),
                {"id": user_id, "created_at": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO transfer_suggestions "
                    "(id, user_id, counterparty_key, kind, status, created_at) "
                    "VALUES (:id, :user_id, 'phase4-smoke', 'family', 'pending', :created_at)"
                ),
                {"id": suggestion_id, "user_id": user_id, "created_at": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO classification_corrections "
                    "(id, user_id, counterparty_key, category, confirmed, created_at) "
                    "VALUES (:id, :user_id, 'phase4-smoke', 'Transport', true, :created_at)"
                ),
                {"id": correction_id, "user_id": user_id, "created_at": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO reviewed_global_rules "
                    "(id, narration_hash, category, reviewed_at) "
                    "VALUES (:id, :hash, 'Transport', :reviewed_at)"
                ),
                {"id": rule_id, "hash": uuid4().hex * 2, "reviewed_at": now},
            )
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 4 PostgreSQL check passed at revision 0019; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
