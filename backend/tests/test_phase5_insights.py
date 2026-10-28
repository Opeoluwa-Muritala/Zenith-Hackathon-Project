"""Phase 5 INS requirement coverage."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.insights.business import suggest_use
from app.insights.detectors.cash_flow_profile import detect as cash_flow
from app.insights.detectors.health_snapshot import detect as health
from app.insights.detectors.leak_finder import detect as leak_finder
from app.insights.types import Balance, LedgerView, Series, Settings, Tx
from app.models import (
    Account,
    AccountType,
    Base,
    Consent,
    InsightAlert,
    Institution,
    Transaction,
    TransactionUseLabel,
    User,
)

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_INS_1_INS_3_INS_4_compute_leaks_cashflow_and_health_in_code():
    transactions = (
        Tx("a", NOW - timedelta(days=2), 50_000, "debit", "Food & Dining", "Shop"),
        Tx("b", NOW - timedelta(days=1), 50_000, "debit", "Food & Dining", "Shop"),
        Tx("c", NOW - timedelta(days=8), 500_000, "credit", "Uncategorised", "Client"),
    )
    recurring = Series(
        "s",
        "Stream",
        "Bills & Utilities",
        30,
        20_000,
        20_000,
        20_000,
        4,
        NOW + timedelta(days=2),
        subscription_like=True,
    )
    view = LedgerView(transactions, (Balance("account", 900_000, "current"),), (recurring,))
    leak = leak_finder(view, Settings(), NOW)[0]
    profile = cash_flow(view, Settings(), NOW)[0]
    snapshot = health(view, Settings(profile_mode="sme"), NOW)[0]
    assert leak.payload["amount_minor"] == 70_000
    assert set(leak.payload["transaction_ids"]) >= {"a", "b"}
    assert profile.payload["inflow_minor"] == 500_000
    assert profile.payload["outflow_minor"] == 100_000
    assert profile.payload["runway_days"] is not None
    assert snapshot.payload["mode"] == "sme"
    assert len(snapshot.payload["drivers"]) == 3
    assert 0 <= snapshot.payload["score"] <= 100


def test_INS_2_suggestions_are_conservative_and_explain_confidence():
    personal = Transaction(category="Food & Dining", decoded_merchant="Cafe")
    business = Transaction(category="Bills & Utilities", decoded_merchant="VAT")
    unsure = Transaction(category="Transfers & Family", decoded_merchant="Unknown")
    assert suggest_use(personal) == ("personal", 8000)
    assert suggest_use(business) == ("business", 8500)
    assert suggest_use(unsure) == ("unsure", 4000)


def test_INS_2_INS_6_migration_0020_is_reversible():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0020_phase5_insights.py"
    spec = importlib.util.spec_from_file_location("phase5_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(inspect(connection).get_table_names())
        assert {"insight_profiles", "transaction_use_labels", "insight_alerts"} <= tables
        migration.downgrade()
        assert "insight_profiles" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_INS_2_INS_5_INS_6_INS_7_owner_review_cards_and_alerts(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        user = User(id=uuid4(), created_at=NOW)
        bank = Institution(name="Fixture", code="P5", savings_rate_bps=0)
        db.add_all([user, bank])
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="Fixture",
            scope="transactions:read",
            granted_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        account = Account(
            user_id=user.id,
            institution_id=bank.id,
            consent_id=consent.id,
            account_number_masked="0000",
            type=AccountType.current,
            current_balance_minor=800_000,
        )
        db.add(account)
        await db.flush()
        for index, posted in enumerate((NOW - timedelta(hours=2), NOW - timedelta(hours=1))):
            db.add(
                Transaction(
                    account_id=account.id,
                    posted_at=posted,
                    amount_minor=40_000,
                    direction="debit",
                    narration_raw="POS CAFE",
                    narration_clean="POS CAFE",
                    category="Food & Dining",
                    channel="POS",
                    dedupe_hash=f"hash-{index}",
                    decoded_merchant="Cafe",
                    parse_confidence_bps=6500,
                )
            )
        await db.commit()
        transaction_id = (await db.scalars(select(Transaction.id))).first()

    async def database():
        async with sessions() as db:
            yield db

    async def identity():
        return user

    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[current_user] = identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            assert (await client.get("/business-personal/review")).status_code == 409
            assert (await client.put("/insight-profile", json={"mode": "sme"})).status_code == 200
            review = (await client.get("/business-personal/review")).json()
            assert review["items"][0]["suggested_label"] == "personal"
            corrected = await client.put(
                f"/business-personal/transactions/{transaction_id}", json={"label": "business"}
            )
            assert corrected.json()["effective_label"] == "business"
            run = await client.post("/insights/run")
            assert run.status_code == 200
            cards = (await client.get("/insights")).json()
            headline = next(item for item in cards if item["kind"] == "leak_finder_headline")
            assert headline["number_minor"] == 40_000
            assert len(headline["evidence_transaction_ids"]) == 2
            assert headline["confidence_label"] == "low"
            assert headline["why_it_matters"] and headline["action"]
            alerts = (await client.get("/insight-alerts")).json()
            assert alerts[0]["kind"] == "new_leak"
            assert (await client.post(f"/insight-alerts/{alerts[0]['id']}/read")).status_code == 200
        async with sessions() as db:
            assert (
                await db.scalars(select(TransactionUseLabel))
            ).one().confirmed_label == "business"
            assert (await db.scalars(select(InsightAlert))).first() is not None
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
