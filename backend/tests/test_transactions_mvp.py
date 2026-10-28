"""Transaction rules, direction filtering and spending read only owned accounts."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.insights.detectors.velocity_warning import projected_month_end_spend
from app.ledger.service import ingest
from app.models import (
    Account,
    AccountType,
    Base,
    CategoryRule,
    CategorySource,
    Consent,
    Institution,
    Transaction,
    User,
)
from app.providers.base import ProviderTransaction


def test_budget_projection_reuses_velocity_calendar_math():
    assert projected_month_end_spend(2800, datetime(2026, 2, 14, tzinfo=UTC)) == 5600


@pytest.mark.asyncio
async def test_reclassification_rule_applies_to_future_sync_and_analytics():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime.now(UTC)
    async with sessions() as db:
        user = User(phone="+2348000000060", email=None, created_at=now)
        institution = Institution(name="Fake Bank", code="FAKE", savings_rate_bps=0)
        db.add_all([user, institution])
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="FAKE",
            scope="auth",
            granted_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        account = Account(
            user_id=user.id,
            institution_id=institution.id,
            consent_id=consent.id,
            account_number_masked="******1234",
            type=AccountType.current,
            currency="NGN",
            current_balance_minor=500_000,
        )
        db.add(account)
        await db.flush()
        first = ProviderTransaction("fake_1", now, 1000, "debit", "NIP/POS/CHOWDECK", None, None)
        assert await ingest(db, account, [first]) == 1
        assert await ingest(db, account, [first]) == 0
        await db.commit()
        tx = (await db.execute(select(Transaction))).scalar_one()
        transaction_id = tx.id

    async def db_override():
        async with sessions() as db:
            yield db

    async def user_override():
        return user

    main.app.dependency_overrides[get_db] = db_override
    main.app.dependency_overrides[current_user] = user_override
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            changed = await client.patch(
                f"/transactions/{transaction_id}/category",
                json={"category": "Food & Dining", "apply_to_future": True},
            )
            assert changed.status_code == 200
            assert changed.json()["category_source"] == "user_rule"
            assert len((await client.get("/category-rules")).json()) == 1
            assert len((await client.get("/transactions?type=debit")).json()) == 1
            assert (await client.get("/transactions?type=credit")).json() == []
            tx_response = (await client.get("/transactions?type=debit")).json()[0]
            assert tx_response["raw_narration"] == "NIP/POS/CHOWDECK"
            assert tx_response["decoded_merchant"] == "Chowdeck"
            recent = await client.get("/transactions/recent")
            assert recent.status_code == 200
            analytics = await client.get("/analytics/spending?period=this_month")
            assert analytics.status_code == 200
            assert analytics.json()["total_outflow_minor"] == 1000
            assert (await client.get("/budget/velocity")).status_code == 404
            set_budget = await client.put("/budget", json={"monthly_limit_minor": 5000})
            assert set_budget.status_code == 200
            velocity = await client.get("/budget/velocity")
            assert velocity.status_code == 200
            assert velocity.json()["spent_minor"] == 1000
            assert velocity.json()["monthly_limit_minor"] == 5000
            obligation = await client.post(
                "/obligations",
                json={
                    "lender_name": "Fake Lender",
                    "kind": "loan",
                    "amount_minor": 1000,
                    "cadence_days": 30,
                    "next_due_date": (now + timedelta(days=1)).date().isoformat(),
                    "account_id": str(account.id),
                },
            )
            assert obligation.status_code == 201
            obligation_id = obligation.json()["id"]
            assert (await client.get(f"/obligations/{obligation_id}")).json()["payments"] == []
            assert len((await client.get("/obligations")).json()) == 1
            dismissed = await client.patch(
                f"/obligations/{obligation_id}", json={"status": "dismissed"}
            )
            assert dismissed.status_code == 200
            assert (await client.get("/obligations")).json() == []
        async with sessions() as db:
            assert (
                await db.execute(select(CategoryRule))
            ).scalar_one().counterparty_key == "chowdeck"
            assert (
                await ingest(
                    db,
                    account,
                    [ProviderTransaction("fake_2", now, 2000, "debit", "POS CHOWDECK", None, None)],
                )
                == 1
            )
            latest = (
                await db.execute(select(Transaction).where(Transaction.amount_minor == 2000))
            ).scalar_one()
            assert latest.category == "Food & Dining"
            assert latest.category_source == CategorySource.user_rule
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
