"""Exercise the complete seeded ledger without a local database service."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main as main_module
from app.insights.runner import run_for_user
from app.ledger.service import ledger_view
from app.main import insight_is_authorised
from app.models import Base, Consent, InsightRecord, User
from scripts.seed import __main__ as seed_module


@pytest.mark.asyncio
async def test_seeded_personas_and_revocation(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    monkeypatch.setattr(seed_module, "SessionLocal", sessions)
    monkeypatch.setattr(seed_module, "now_utc", lambda: now)
    monkeypatch.setattr(main_module, "now_utc", lambda: now)
    await seed_module.seed()
    expected = {
        "salaried": {
            "safe_to_spend",
            "bill_spike",
            "temporal_spending_spikes",
            "idle_cash_optimisation",
            "found_money_redirection",
        },
        "freelancer": {
            "income_expense_crossover",
            "zombie_subscription",
            "double_charge_price_change",
            "renewal_countdown",
        },
        "student": {"merchant_monopoly", "velocity_warning", "opportunity_cost_swap"},
    }
    async with sessions() as db:
        for persona, phone, *_ in seed_module.PERSONAS:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
            kinds = set(
                (
                    await db.execute(
                        select(InsightRecord.kind).where(InsightRecord.user_id == user.id)
                    )
                ).scalars()
            )
            assert expected[persona] <= kinds, (persona, expected[persona] - kinds)
            view, settings = await ledger_view(db, user.id, now)
            assert view.transactions and view.balances and settings
            if persona == "student":
                stored_insight = (
                    (
                        await db.execute(
                            select(InsightRecord).where(InsightRecord.user_id == user.id)
                        )
                    )
                    .scalars()
                    .first()
                )
                assert stored_insight and await insight_is_authorised(db, user.id, stored_insight)
                consent = (
                    await db.execute(select(Consent).where(Consent.user_id == user.id))
                ).scalar_one()
                consent.revoked_at = now
                await db.flush()
                revoked_view, _ = await ledger_view(db, user.id, now)
                assert not revoked_view.transactions and not revoked_view.balances
                assert not await insight_is_authorised(db, user.id, stored_insight)
                assert await run_for_user(db, user.id, now) == 0
    await engine.dispose()
