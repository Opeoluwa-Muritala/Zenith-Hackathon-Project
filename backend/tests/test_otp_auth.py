"""Exercise the real one-time-code lifecycle without external services."""

from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.identity.otp import _development_inbox, code_matches
from app.models import Base, OtpCode, SecurityAuditEvent, User


@pytest.mark.asyncio
async def test_mock_bvn_shortcut_is_unavailable_in_production(monkeypatch):
    monkeypatch.setattr(main.settings, "environment", "production")
    with pytest.raises(HTTPException) as error:
        await main.verify_bvn(main.BvnIn(bvn="0" * 11), User(phone=None), None)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_AUTH_1_AUTH_3_AUTH_4_otp_lifecycle_and_session_revocation(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def db_override():
        async with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(main.settings, "otp_sender", "dev_inbox")
    monkeypatch.setattr(main.settings, "otp_dev_inbox_enabled", True)
    monkeypatch.setattr(main.settings, "jwt_secret", "unit-test-jwt-key-with-at-least-32-bytes")
    monkeypatch.setattr(main.settings, "otp_secret", "unit-test-otp-key-with-at-least-32-bytes")
    main.get_rate_limiter.cache_clear()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            request = await client.post("/auth/otp/request", json={"phone": "08000000000"})
            assert request.status_code == 202
            identifier = "+2348000000000"
            code = _development_inbox[identifier]
            async with sessions() as db:
                row = (await db.execute(select(OtpCode))).scalar_one()
                assert code != row.code_hash
                assert code_matches(identifier, code, row.salt, row.code_hash)
            wrong_code = "000000" if code != "000000" else "111111"
            wrong = await client.post(
                "/auth/otp/verify", json={"phone": identifier, "otp": wrong_code}
            )
            assert wrong.status_code == 401
            verified = await client.post(
                "/auth/otp/verify", json={"phone": identifier, "otp": code}
            )
            assert verified.status_code == 200
            tokens = verified.json()
            replay = await client.post("/auth/otp/verify", json={"phone": identifier, "otp": code})
            assert replay.status_code == 401
            async with sessions() as db:
                assert (await db.execute(select(User))).scalar_one().phone == identifier
                events = (await db.execute(select(SecurityAuditEvent.event))).scalars().all()
                assert {"auth.otp_requested", "auth.login_failed", "auth.login"} <= set(events)
            auth = {"Authorization": "Bearer " + tokens["access_token"]}
            assert (await client.post("/auth/logout-all", headers=auth)).status_code == 204
            assert (await client.post("/auth/logout-all", headers=auth)).status_code == 401
            assert (
                await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            ).status_code == 401
    finally:
        main.app.dependency_overrides.clear()
        main.get_rate_limiter.cache_clear()
        _development_inbox.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_AUTH_1_expired_code_cannot_be_used(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def db_override():
        async with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(main.settings, "otp_sender", "dev_inbox")
    monkeypatch.setattr(main.settings, "otp_dev_inbox_enabled", True)
    main.get_rate_limiter.cache_clear()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            identifier = "+2348000000001"
            assert (
                await client.post("/auth/otp/request", json={"phone": identifier})
            ).status_code == 202
            code = _development_inbox[identifier]
            async with sessions() as db:
                row = (await db.execute(select(OtpCode))).scalar_one()
                row.expires_at -= timedelta(minutes=10)
                await db.commit()
            assert (
                await client.post("/auth/otp/verify", json={"phone": identifier, "otp": code})
            ).status_code == 401
    finally:
        main.app.dependency_overrides.clear()
        main.get_rate_limiter.cache_clear()
        _development_inbox.clear()
        await engine.dispose()
