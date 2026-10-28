"""Short-lived one-time codes and configured delivery adapters."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Protocol

import httpx

from app.core.clock import now_utc
from app.core.config import get_settings

_development_secret = secrets.token_urlsafe(48)
_development_inbox: dict[str, str] = {}
_inbox_expires: dict[str, datetime] = {}


def forget_code(identifier: str) -> None:
    _development_inbox.pop(identifier, None)
    _inbox_expires.pop(identifier, None)


def inbox_code(identifier: str) -> str | None:
    expiry = _inbox_expires.get(identifier)
    if expiry is None or expiry <= now_utc():
        forget_code(identifier)
        return None
    return _development_inbox.get(identifier)


def expire_inbox_entry(identifier: str, expiry: datetime) -> None:
    # A timer for an older resend must not delete its replacement code.
    if _inbox_expires.get(identifier) == expiry:
        forget_code(identifier)


def cleanup_expired_inbox() -> int:
    """Remove expired entries in this process; normal timers remain the primary cleanup."""
    expired = [identifier for identifier, expiry in _inbox_expires.items() if expiry <= now_utc()]
    for identifier in expired:
        forget_code(identifier)
    return len(expired)


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def new_salt() -> str:
    return secrets.token_hex(16)


def code_digest(identifier: str, code: str, salt: str) -> str:
    secret = get_settings().otp_secret or _development_secret
    return hmac.new(
        secret.encode(), f"{identifier}|{salt}|{code}".encode(), hashlib.sha256
    ).hexdigest()


def code_matches(identifier: str, code: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(code_digest(identifier, code, salt), expected)


class OtpSender(Protocol):
    async def send(self, identifier: str, code: str) -> None: ...


class DevInboxSender:
    async def send(self, identifier: str, code: str) -> None:
        if not get_settings().otp_dev_inbox_enabled or get_settings().environment == "production":
            raise RuntimeError("Development OTP inbox is disabled")
        _development_inbox[identifier] = code
        _inbox_expires[identifier] = now_utc() + timedelta(
            seconds=get_settings().otp_expiry_seconds
        )
        asyncio.get_running_loop().call_later(
            get_settings().otp_expiry_seconds,
            expire_inbox_entry,
            identifier,
            _inbox_expires[identifier],
        )


class HttpOtpSender:
    async def send(self, identifier: str, code: str) -> None:
        settings = get_settings()
        if not settings.otp_http_url:
            raise RuntimeError("OTP HTTP sender is not configured")
        if "@" not in identifier:
            raise RuntimeError("Configured OTP sender supports email only")
        if settings.environment == "production" and not settings.otp_http_url.startswith(
            "https://"
        ):
            raise RuntimeError("OTP HTTP sender must use HTTPS")
        headers = {}
        if settings.otp_http_key:
            headers["Authorization"] = f"Bearer {settings.otp_http_key}"
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(
                    settings.otp_http_url,
                    headers=headers,
                    json={
                        "to": identifier,
                        "subject": "Your Fetch sign-in code",
                        "text": (
                            f"Your Fetch sign-in code is {code}. "
                            f"It expires in {settings.otp_expiry_seconds // 60} minutes."
                        ),
                    },
                )
            except httpx.RequestError:
                raise RuntimeError("OTP delivery failed") from None
            if response.is_error:
                raise RuntimeError("OTP delivery failed")


def sender() -> OtpSender:
    settings = get_settings()
    if settings.otp_sender == "http":
        return HttpOtpSender()
    if settings.otp_sender == "dev_inbox" and settings.otp_dev_inbox_enabled:
        return DevInboxSender()
    raise RuntimeError("OTP sender is not configured")
