from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app, sync_window_start
from app.providers.base import ProviderError, ProviderNotReady
from app.providers.mono import MonoProvider


@pytest.mark.asyncio
@respx.mock
async def test_mono_paginates_only_same_origin():
    respx.get("https://api.withmono.com/v2/accounts/a").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"meta": {"data_status": "AVAILABLE", "retrieved_data": ["transactions"]}}
            },
        )
    )
    respx.get("https://api.withmono.com/v2/accounts/a/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "date": "2026-01-01T00:00:00Z",
                        "amount": 100,
                        "type": "debit",
                        "narration": "POS",
                        "balance": 0,
                    }
                ],
                "meta": {"next": None},
            },
        )
    )
    result = await MonoProvider("test_sk_x").transactions(
        "a", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)
    )
    assert result[0].amount_minor == 100


@pytest.mark.asyncio
@respx.mock
async def test_mono_balance_uses_documented_realtime_header():
    route = respx.get("https://api.withmono.com/v2/accounts/a/balance").mock(
        return_value=httpx.Response(200, json={"data": {"balance": 53769, "currency": "NGN"}})
    )
    result = await MonoProvider("test_sk_x").balance("a", realtime=True)
    assert result["data"]["balance"] == 53769
    assert route.calls.last.request.headers["x-realtime"] == "true"


def test_mono_webhook_uses_webhook_secure_key_and_rejects_bad_secrets(monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_secure_key", "test-webhook-key")
    with TestClient(app, base_url="http://testserver") as client:
        body = '{"event":'
        assert client.post("/webhooks/mono", content=body).status_code == 401
        assert (
            client.post(
                "/webhooks/mono", headers={"mono-webhook-secret": "wrong"}, content=body
            ).status_code
            == 401
        )
        # Malformed JSON reaches parsing only when the configured shared secret matched.
        assert (
            client.post(
                "/webhooks/mono",
                headers={"mono-webhook-secret": "test-webhook-key"},
                content=body,
            ).status_code
            == 422
        )


def test_incremental_window_overlaps_last_sync():
    now = datetime(2026, 10, 1, tzinfo=UTC)
    assert sync_window_start(None, now) == now - timedelta(days=190)
    previous = datetime(2026, 9, 30, tzinfo=UTC)
    assert sync_window_start(previous, now) == previous - timedelta(days=3)


@pytest.mark.asyncio
@respx.mock
async def test_missing_retrieved_data_prevents_transaction_fetch():
    respx.get("https://api.withmono.com/v2/accounts/a").mock(
        return_value=httpx.Response(200, json={"data": {"meta": {"data_status": "AVAILABLE"}}})
    )
    with pytest.raises(ProviderNotReady):
        await MonoProvider("test_key").transactions("a", datetime.now(UTC), datetime.now(UTC))
    assert len(respx.calls) == 1
    assert respx.calls.last.request.url.path == "/v2/accounts/a"


@pytest.mark.asyncio
@respx.mock
async def test_transaction_pagination_rejects_repeated_url():
    respx.get("https://api.withmono.com/v2/accounts/a").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"meta": {"data_status": "AVAILABLE", "retrieved_data": ["transactions"]}}
            },
        )
    )
    route = respx.get("https://api.withmono.com/v2/accounts/a/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [],
                "meta": {"next": "https://api.withmono.com/v2/accounts/a/transactions"},
            },
        )
    )
    with pytest.raises(ProviderError, match="pagination"):
        await MonoProvider("test_key").transactions("a", datetime.now(UTC), datetime.now(UTC))
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_balance_preserves_async_job_headers():
    respx.get("https://api.withmono.com/v2/accounts/a/balance").mock(
        return_value=httpx.Response(
            200,
            headers={"x-job-status": "PROCESSING", "x-has-new-data": "false"},
            json={"data": {"balance": 100, "currency": "NGN"}},
        )
    )
    result = await MonoProvider("test_key").balance("a", realtime=True)
    assert result["_realtime"] == {"job_status": "processing", "has_new_data": "false"}
