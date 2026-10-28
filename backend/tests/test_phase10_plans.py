"""Phase 10 BIL requirement coverage without payment processing."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.models import Base, Consent, ProviderLink, UpgradeTapEvent, User, UserPlan
from app.plans.service import require_live_sync

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_BIL_1_BIL_2_BIL_4_migration_0025_is_reversible():
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0025_phase10_plans_billing.py"
    spec = importlib.util.spec_from_file_location("phase10_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Uuid(), primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {"user_plans", "upgrade_tap_events"} <= set(inspect(connection).get_table_names())
        migration.downgrade()
        assert "user_plans" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_BIL_1_BIL_2_live_sync_trial_account_limit_and_paid_override():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        user = User(email="plans@example.test", created_at=NOW)
        db.add(user)
        await db.flush()
        plan = await require_live_sync(db, user.id, NOW, new_account=True)
        assert plan.trial_started_at == NOW
        assert plan.trial_ends_at == NOW + timedelta(days=14)
        for index in range(2):
            consent = Consent(
                user_id=user.id,
                institution=f"Fixture {index}",
                scope="transactions:read",
                granted_at=NOW,
                expires_at=NOW + timedelta(days=30),
            )
            db.add(consent)
            await db.flush()
            db.add(
                ProviderLink(
                    user_id=user.id,
                    consent_id=consent.id,
                    provider="mono",
                    status="connected",
                    created_at=NOW,
                )
            )
        await db.flush()
        with pytest.raises(HTTPException) as capped:
            await require_live_sync(db, user.id, NOW, new_account=True)
        assert capped.value.status_code == 402
        plan.trial_ends_at = NOW - timedelta(seconds=1)
        with pytest.raises(HTTPException) as expired:
            await require_live_sync(db, user.id, NOW)
        assert expired.value.status_code == 402
        plan.paid_sme = True
        assert await require_live_sync(db, user.id, NOW, new_account=True) is plan
    await engine.dispose()


@pytest.mark.asyncio
async def test_BIL_2_BIL_3_BIL_4_plan_contract_and_upgrade_tap_logging():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        user = User(email="upgrade@example.test", created_at=NOW)
        db.add(user)
        await db.commit()

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
            free = await client.get("/plan")
            assert free.status_code == 200
            body = free.json()
            assert body["tier"] == "free" and body["trial_status"] == "not_started"
            assert body["free_live_account_limit"] == 2
            assert body["entitlements"]["statement_upload"] is True
            assert body["entitlements"]["lender_ready_reports"] is False
            recorded = await client.post(
                "/billing/upgrade-events",
                json={"surface": "report", "desired_tier": "sme"},
            )
            assert recorded.status_code == 202
            assert recorded.json() == {"status": "recorded"}
    finally:
        main.app.dependency_overrides.clear()
    async with sessions() as db:
        event = (await db.scalars(select(UpgradeTapEvent))).one()
        assert event.surface == "report" and event.desired_tier == "sme"
        plan = await db.get(UserPlan, user.id)
        assert plan is not None and plan.paid_sme is False
    await engine.dispose()
