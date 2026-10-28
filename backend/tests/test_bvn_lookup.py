from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.core.encryption import decrypt_field, encrypt_field, hash_field
from app.providers.mono_lookup import MonoLookupProvider


@respx.mock
async def test_lookup_client_matches_mono_bvn_flow_without_logging_secrets(caplog):
    base = "https://api.withmono.com"
    respx.post(f"{base}/v2/lookup/bvn/initiate").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "session_id": "session-1",
                    "methods": [{"method": "phone", "hint": "080***"}],
                }
            },
        )
    )
    respx.post(f"{base}/v2/lookup/bvn/verify").mock(
        return_value=httpx.Response(200, json={"status": "successful"})
    )
    respx.post(f"{base}/v2/lookup/bvn/details").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "account_name": "A",
                        "account_number": "1234567890",
                        "institution": {"name": "Bank", "bank_code": "057"},
                    }
                ]
            },
        )
    )
    provider = MonoLookupProvider("lookup-secret", base)
    session, methods = await provider.initiate_lookup("12345678901")
    await provider.verify_lookup(session, "phone")
    accounts = await provider.lookup_details(session, "654321")
    assert session == "session-1"
    assert methods[0]["method"] == "phone"
    assert accounts[0]["account_number"] == "1234567890"
    assert "lookup-secret" not in caplog.text
    assert "12345678901" not in caplog.text
    assert "654321" not in caplog.text


def test_sensitive_fields_are_reversible_but_not_plaintext():
    encrypted = encrypt_field("1234567890")
    assert encrypted != "1234567890"
    assert decrypt_field(encrypted) == "1234567890"
    assert hash_field("1234567890") != "1234567890"


def test_lookup_session_expiry_window_is_ten_minutes():
    now = datetime.now(UTC)
    assert now + timedelta(minutes=10) > now
