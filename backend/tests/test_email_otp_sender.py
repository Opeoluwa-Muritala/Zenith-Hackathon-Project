from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.identity.otp import HttpOtpSender


def test_AUTH_email_url_environment_alias_is_supported():
    assert Settings(EMAIL_URL="https://emailope.vercel.app/").otp_http_url == (
        "https://emailope.vercel.app/"
    )


@pytest.mark.asyncio
async def test_AUTH_email_http_sender_uses_fetch_email_contract(monkeypatch):
    settings = SimpleNamespace(
        otp_http_url="https://emailope.vercel.app/",
        otp_http_key="",
        environment="staging",
        otp_expiry_seconds=300,
    )
    monkeypatch.setattr("app.identity.otp.get_settings", lambda: settings)
    with respx.mock:
        route = respx.post("https://emailope.vercel.app/").mock(return_value=Response(200))
        await HttpOtpSender().send("tester@example.com", "123456")

        payload = route.calls.last.request.content.decode()
        assert '"to":"tester@example.com"' in payload
        assert '"subject":"Your Fetch sign-in code"' in payload
        assert "123456" in payload
        assert "authorization" not in route.calls.last.request.headers


@pytest.mark.asyncio
async def test_AUTH_email_http_sender_rejects_phone_recipient(monkeypatch):
    settings = SimpleNamespace(
        otp_http_url="https://emailope.vercel.app/",
        otp_http_key="",
        environment="staging",
        otp_expiry_seconds=300,
    )
    monkeypatch.setattr("app.identity.otp.get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="email only"):
        await HttpOtpSender().send("+2348000000000", "123456")
