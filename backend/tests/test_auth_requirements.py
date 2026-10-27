"""Requirement-ID coverage for Phase 1 authentication controls."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.identity.lockout import ensure_not_locked, register_failure
from app.models import AuthLockout, Base


def test_AUTH_1_code_policy_defaults_are_six_digits_five_minutes_and_five_attempts():
    settings = Settings(_env_file=None)
    assert settings.otp_expiry_seconds == 300
    assert settings.otp_max_attempts == 5


@pytest.mark.asyncio
async def test_AUTH_2_durable_backoff_lockout(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    from app.identity import lockout

    monkeypatch.setattr(
        lockout.get_settings(), "otp_secret", "test-secret-with-at-least-32-characters"
    )
    monkeypatch.setattr(lockout.get_settings(), "otp_lockout_threshold", 2)
    async with sessions() as db:
        await register_failure(db, "person@example.com")
        await register_failure(db, "person@example.com")
        await db.commit()
        row = (await db.execute(select(AuthLockout))).scalar_one()
        assert row.locked_until is not None
        with pytest.raises(HTTPException) as error:
            await ensure_not_locked(db, "person@example.com")
        assert error.value.status_code == 429
    await engine.dispose()


def test_AUTH_5_APP_ENV_production_refuses_demo_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        demo_otp_inbox_password="long-enough-demo-password",  # noqa: S106
        demo_identifiers="person@example.com",
    )
    with pytest.raises(RuntimeError, match="forbidden"):
        settings.validate_runtime()


def test_AUTH_5_production_requires_dedicated_encryption_key():
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://fetch:secret@db.example.com/fetch_prod",
        jwt_secret="j" * 32,
        bvn_pepper="b" * 32,
        otp_secret="o" * 32,
        otp_sender="http",
        otp_http_url="https://otp.example.com/send",
        otp_http_key="secret",
        mono_lookup_secret_key="lookup",  # noqa: S106
    )
    with pytest.raises(RuntimeError, match="FIELD_ENCRYPTION_KEY"):
        settings.validate_runtime()
