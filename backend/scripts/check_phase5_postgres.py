"""Non-destructive Phase 5 smoke check against configured PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models import (
    Account,
    AccountType,
    Channel,
    Consent,
    Direction,
    InsightAlert,
    InsightProfile,
    InsightRecord,
    Institution,
    Transaction,
    TransactionUseLabel,
    User,
)


async def check() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0020":
            raise RuntimeError(f"Expected revision 0020, found {revision!r}")
        await db.rollback()
        transaction = await db.begin()
        try:
            suffix = uuid4().hex[:12]
            user = User(created_at=now)
            institution = Institution(
                name=f"Phase 5 smoke {suffix}", code=f"P5{suffix}", savings_rate_bps=0
            )
            db.add_all((user, institution))
            await db.flush()
            consent = Consent(
                user_id=user.id,
                institution=institution.name,
                scope="transactions:read",
                granted_at=now,
                expires_at=now + timedelta(minutes=5),
            )
            db.add(consent)
            await db.flush()
            account = Account(
                user_id=user.id,
                institution_id=institution.id,
                consent_id=consent.id,
                account_number_masked="****0000",
                type=AccountType.current,
                current_balance_minor=100_000,
            )
            db.add(account)
            await db.flush()
            ledger_item = Transaction(
                account_id=account.id,
                posted_at=now,
                amount_minor=10_000,
                direction=Direction.debit,
                narration_raw="phase 5 smoke",
                narration_clean="phase 5 smoke",
                category="Uncategorised",
                channel=Channel.OTHER,
                dedupe_hash=uuid4().hex * 2,
            )
            insight = InsightRecord(
                user_id=user.id,
                module="leaks",
                kind="leak_finder_headline",
                severity="warning",
                title="Phase 5 smoke",
                body="Rollback-only smoke check.",
                payload_json={"source_account_ids": [str(account.id)]},
                dedupe_key=f"phase5-smoke:{suffix}",
                created_at=now,
            )
            db.add_all((ledger_item, insight))
            await db.flush()
            db.add_all(
                (
                    InsightProfile(user_id=user.id, mode="sme", updated_at=now),
                    TransactionUseLabel(
                        transaction_id=ledger_item.id,
                        user_id=user.id,
                        suggested_label="unsure",
                        confidence_bps=4000,
                        confirmed_label="business",
                        updated_at=now,
                    ),
                    InsightAlert(
                        user_id=user.id,
                        insight_id=insight.id,
                        kind="new_leak",
                        severity="warning",
                        what_changed="Smoke check",
                        suggested_response="No action",
                        created_at=now,
                    ),
                )
            )
            await db.flush()
        finally:
            await transaction.rollback()
    await engine.dispose()
    print("Phase 5 PostgreSQL check passed at revision 0020; smoke rows rolled back.")


if __name__ == "__main__":
    asyncio.run(check())
