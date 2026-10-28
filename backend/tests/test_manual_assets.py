"""Manual asset valuation and reminder cadence have no implicit exchange rate."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.assets.fx import convert_minor, rate_to_ppm
from app.assets.service import asset_value_ngn_minor, next_reminder
from app.core.db import get_db
from app.core.security import current_user
from app.models import Base, ManualAsset, UpdateCadence, User


def test_usd_asset_uses_stored_ppm_rate_and_integer_minor_units():
    rate = rate_to_ppm(Decimal("1500.25"))
    assert rate == 1_500_250_000
    assert convert_minor(100, rate) == 150_025
    asset = ManualAsset(currency="USD", amount_minor=100, fx_rate_used=rate)
    assert asset_value_ngn_minor(asset) == 150_025
    with pytest.raises(ValueError):
        rate_to_ppm(Decimal("0"))
    with pytest.raises(ValueError):
        asset_value_ngn_minor(ManualAsset(currency="USD", amount_minor=100, fx_rate_used=None))


def test_monthly_reminder_clamps_short_month():
    start = datetime(2026, 1, 31, tzinfo=UTC)
    assert next_reminder(start, UpdateCadence.monthly) == datetime(2026, 2, 28, tzinfo=UTC)
    assert next_reminder(start, UpdateCadence.biweekly) == datetime(2026, 2, 14, tzinfo=UTC)


@pytest.mark.asyncio
async def test_asset_crud_and_net_position_use_stored_fx_rate():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        user = User(phone="+2348000000040", email=None, created_at=datetime.now(UTC))
        db.add(user)
        await db.commit()

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
            missing_rate = await client.post(
                "/assets",
                json={
                    "platform": "bamboo",
                    "category": "us_equities",
                    "currency": "USD",
                    "amount_minor": 100,
                    "update_cadence": "monthly",
                },
            )
            assert missing_rate.status_code == 422
            created = await client.post(
                "/assets",
                json={
                    "platform": "bamboo",
                    "category": "us_equities",
                    "currency": "USD",
                    "amount_minor": 100,
                    "fx_rate": "1500.25",
                    "update_cadence": "monthly",
                },
            )
            assert created.status_code == 201
            asset_id = created.json()["id"]
            assert created.json()["value_ngn_minor"] == 150_025
            assert len((await client.get("/assets")).json()) == 1
            assert (await client.get("/net-position")).json()["total_minor"] == 150_025
            updated = await client.put(
                f"/assets/{asset_id}",
                json={
                    "platform": "cowrywise",
                    "category": "mutual_funds",
                    "currency": "NGN",
                    "amount_minor": 200_000,
                    "update_cadence": "biweekly",
                },
            )
            assert updated.json()["value_ngn_minor"] == 200_000
            assert (await client.delete(f"/assets/{asset_id}")).status_code == 204
            assert (await client.get("/assets")).json() == []
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
