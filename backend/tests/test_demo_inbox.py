"""Hosted presenter access is explicit, allowlisted and ephemeral."""

from datetime import timedelta

import httpx
import pytest

from app import main
from app.core.clock import now_utc
from app.core.config import Settings
from app.identity.otp import DevInboxSender, _inbox_expires, forget_code, inbox_code


@pytest.mark.asyncio
async def test_presenter_page_requires_basic_auth_and_allowlisted_identity(monkeypatch):
    monkeypatch.setattr(main.settings, "demo_mode", True)
    monkeypatch.setattr(main.settings, "demo_otp_inbox_password", "test-only-presenter-password")
    monkeypatch.setattr(main.settings, "demo_identifiers", "user@example.com")
    monkeypatch.setattr(main.settings, "otp_dev_inbox_enabled", True)
    monkeypatch.setattr(main.settings, "environment", "development")
    await DevInboxSender().send("user@example.com", "123456")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="https://demo.test"
        ) as client:
            assert (await client.get("/dev/otp-inbox/page")).status_code == 401
            auth = httpx.BasicAuth("demo", "test-only-presenter-password")
            page = await client.get("/dev/otp-inbox/page?identifier=user@example.com", auth=auth)
            assert page.status_code == 200 and "123456" in page.text
            assert page.headers["cache-control"] == "no-store"
            assert (
                await client.get("/dev/otp-inbox?identifier=other@example.com", auth=auth)
            ).status_code == 404
            _inbox_expires["user@example.com"] = now_utc() - timedelta(seconds=1)
            assert inbox_code("user@example.com") is None
            monkeypatch.setattr(main.settings, "environment", "production")
            assert (await client.get("/dev/otp-inbox/page", auth=auth)).status_code == 404
    finally:
        forget_code("user@example.com")


def test_AUTH_5_demo_startup_refuses_missing_secrets_and_production():
    with pytest.raises(RuntimeError, match="forbidden"):
        Settings(_env_file=None, demo_mode=True, environment="production").validate_runtime()
    with pytest.raises(RuntimeError, match="password"):
        Settings(_env_file=None, demo_mode=True).validate_runtime()


def test_neon_url_is_normalised_without_connection():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://fake:fake@db.example.com/fetch?sslmode=require&channel_binding=require",
    )
    assert (
        settings.async_database_url
        == "postgresql+asyncpg://fake:fake@db.example.com/fetch?ssl=require"
    )
