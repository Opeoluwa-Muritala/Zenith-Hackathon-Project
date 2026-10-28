"""Device identifiers are deduplicated without storing or returning raw tokens."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.encryption import decrypt_field, hash_field
from app.core.security import current_user
from app.models import Base, DeviceToken, User


@pytest.mark.asyncio
async def test_device_token_encrypted_and_preferences_owned():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        user = User(phone="+2348000000090", email=None, created_at=datetime.now(UTC))
        db.add(user)
        await db.commit()

    async def db_override():
        async with sessions() as db:
            yield db

    async def user_override():
        return user

    main.app.dependency_overrides[get_db] = db_override
    main.app.dependency_overrides[current_user] = user_override
    sample_device_value = "fake_device_value_for_tests_only_123"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/devices", json={"token": sample_device_value, "platform": "android"}
            )
            assert created.status_code == 201
            assert sample_device_value not in created.text
            device_id = created.json()["id"]
            assert (
                await client.post(
                    "/devices", json={"token": sample_device_value, "platform": "android"}
                )
            ).status_code == 201
            assert (await client.get("/notification-preferences")).json() == {
                "overspending_alerts": True,
                "loan_repayment_reminders": True,
                "investment_update_prompts": True,
            }
            changed = await client.put(
                "/notification-preferences",
                json={
                    "overspending_alerts": False,
                    "loan_repayment_reminders": True,
                    "investment_update_prompts": False,
                },
            )
            assert changed.json()["overspending_alerts"] is False
            assert (await client.delete(f"/devices/{device_id}")).status_code == 204
        async with sessions() as db:
            assert (await db.execute(select(DeviceToken))).scalar_one_or_none() is None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            await client.post(
                "/devices", json={"token": sample_device_value, "platform": "android"}
            )
        async with sessions() as db:
            row = (await db.execute(select(DeviceToken))).scalar_one()
            assert row.token_hash == hash_field(sample_device_value)
            assert sample_device_value not in row.token_encrypted
            assert decrypt_field(row.token_encrypted) == sample_device_value
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
