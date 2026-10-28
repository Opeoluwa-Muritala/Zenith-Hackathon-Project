"""Validation and paid requests must not leak secrets or retry silently."""

import httpx
import pytest
import respx

from app import main
from app.providers.base import ProviderUnavailable
from app.providers.mono import MonoProvider
from app.providers.mono_lookup import MonoLookupProvider


@pytest.mark.asyncio
@respx.mock
async def test_paid_requests_are_attempted_once():
    lookup = respx.post("https://api.withmono.com/v2/lookup/bvn/initiate").mock(
        return_value=httpx.Response(503)
    )
    link = respx.post("https://api.withmono.com/v2/accounts/initiate").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(ProviderUnavailable):
        await MonoLookupProvider("test_key").initiate_lookup("0" * 11)
    with pytest.raises(ProviderUnavailable):
        await MonoProvider("test_key").initiate(
            "Fake User", "user@example.com", "fake_ref", "https://app.test"
        )
    assert lookup.call_count == link.call_count == 1


@pytest.mark.asyncio
async def test_validation_does_not_echo_sensitive_inputs():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/auth/otp/verify", json={"phone": "+2348000000000", "otp": "sensitive-invalid-value"}
        )
    assert response.status_code == 422
    assert "sensitive-invalid-value" not in response.text
    assert "input" not in response.text


def test_alternate_phone_validated_before_provider_call():
    with pytest.raises(ValueError):
        main.BvnMethodIn(method="alternate_phone")
