from datetime import UTC, datetime

import httpx
import pytest
import respx

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
