"""Exercise the mobile backend journey using isolated storage and mocked Mono only."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.clock import now_utc
from app.core.db import get_db
from app.core.security import decode_access, hash_secret
from app.identity.otp import inbox_code
from app.models import Account, Base, RefreshToken, Transaction, User, WebhookEvent
from scripts.demo_supplement import supplement


@pytest.mark.asyncio
@respx.mock
async def test_complete_demo_journey(monkeypatch, caplog):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def db_override():
        async with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(main, "SessionLocal", sessions)
    for name, value in {
        "demo_mode": True,
        "demo_identifiers": "user@example.com",
        "otp_sender": "dev_inbox",
        "otp_dev_inbox_enabled": True,
        "environment": "development",
        "aggregator_provider": "mono",
        "mono_secret_key": "fake_connect_key_for_demo_tests_123",
        "mono_lookup_secret_key": "test_lookup_key",
        "webhook_secure_key": "test_webhook_key",
        "fx_provider_url": "",
        "account_refresh_cooldown_seconds": 60,
    }.items():
        monkeypatch.setattr(main.settings, name, value)
    monkeypatch.setattr(main, "_institution_coverage", None)
    main.get_rate_limiter.cache_clear()
    main._refresh_requests.clear()
    base = "https://api.withmono.com"
    initiate = respx.post(base + "/v2/lookup/bvn/initiate").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "session_id": "fake_session",
                    "methods": [{"method": "email", "hint": "Demo email"}],
                }
            },
        )
    )
    respx.post(base + "/v2/lookup/bvn/verify").mock(
        return_value=httpx.Response(200, json={"data": None})
    )
    details = respx.post(base + "/v2/lookup/bvn/details").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "account_name": "Fake User",
                        "account_number": "0" * 10,
                        "account_type": "SAVINGS",
                        "account_designation": "INDIVIDUAL",
                        "institution": {
                            "name": "OPAY DIGITAL SERVICES LIMITED",
                            "bank_code": "00711",
                            "nip_code": "100004",
                        },
                    },
                    {
                        "account_name": "Fake User",
                        "account_number": "1" * 10,
                        "account_type": "SAVINGS",
                        "account_designation": "INDIVIDUAL",
                        "institution": {"name": "Unmapped Demo Bank", "bank_code": "999"},
                    },
                ]
            },
        )
    )
    respx.get(base + "/v3/institutions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "fake_bank",
                        "bank_code": "00711",
                        "auth_methods": [{"type": "internet_banking"}],
                    }
                ]
            },
        )
    )
    respx.post(base + "/v2/accounts/initiate").mock(
        return_value=httpx.Response(200, json={"data": {"mono_url": "https://link.mono.co/fake"}})
    )
    respx.get(base + "/v2/accounts/fake_account").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "meta": {
                        "data_status": "AVAILABLE",
                        "retrieved_data": ["transactions", "balance"],
                    }
                }
            },
        )
    )
    transaction_data = [
        {
            "id": "fake_tx",
            "date": (now_utc() - timedelta(minutes=1)).isoformat(),
            "amount": 1000,
            "type": "debit",
            "narration": "NIP/POS/FLUTTERWAVE/CHOWDECK",
            "balance": 10000000,
        }
    ]
    tx_route = respx.get(base + "/v2/accounts/fake_account/transactions").mock(
        return_value=httpx.Response(200, json={"data": transaction_data, "meta": {"next": None}})
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            assert (
                await client.post("/auth/otp/request", json={"email": "user@example.com"})
            ).status_code == 202
            code = inbox_code("user@example.com")
            login = await client.post(
                "/auth/otp/verify", json={"email": "user@example.com", "otp": code}
            )
            assert login.status_code == 200
            tokens = login.json()
            client.headers["Authorization"] = "Bearer " + tokens["access_token"]
            assert inbox_code("user@example.com") is None
            invalid = await client.post(
                "/onboarding/bvn/start", json={"bvn": "invalid-sensitive-bvn"}
            )
            assert invalid.status_code == 422 and initiate.call_count == 0
            assert "invalid-sensitive-bvn" not in invalid.text
            assert (
                await client.post("/onboarding/bvn/start", json={"bvn": "0" * 11})
            ).status_code == 200
            assert (
                await client.post("/onboarding/bvn/start", json={"bvn": "0" * 11})
            ).status_code == 429
            assert initiate.call_count == 1
            assert (
                await client.post(
                    "/onboarding/bvn/send-otp",
                    json={"method": "email", "session_id": "fake_session"},
                )
            ).status_code == 200
            confirmed = await client.post(
                "/onboarding/bvn/confirm", json={"otp": "654321", "session_id": "fake_session"}
            )
            assert confirmed.status_code == 200
            rows = confirmed.json()
            assert all(
                "id" in row and "account_number" not in row and "balance_minor" not in row
                for row in rows
            )
            assert (
                await client.post("/onboarding/bvn/confirm", json={"otp": "654321"})
            ).status_code == 200
            assert details.call_count == 1
            foreign = await client.post(
                "/onboarding/bvn/send-otp",
                json={"method": "email", "session_id": "foreign_session"},
            )
            assert foreign.status_code == 410
            assert (
                await client.post("/accounts/discovered/select", json={"ids": [rows[0]["id"]]})
            ).json()["skipped"] == 1
            assert len((await client.get("/accounts/skipped")).json()) == 1
            linked = await client.post(
                f"/accounts/discovered/{rows[0]['id']}/link", json={"email": "user@example.com"}
            )
            assert linked.status_code == 200 and linked.json()["institution_mapped"]
            ref = linked.json()["ref"]
            headers = {"mono-webhook-secret": "test_webhook_key"}
            connected = {
                "event": "mono.events.account_connected",
                "event_id": "fake_connected",
                "data": {"id": "fake_account", "meta": {"ref": ref, "data_status": "PROCESSING"}},
            }
            assert (
                await client.post("/webhooks/mono", json=connected, headers=headers)
            ).status_code == 200
            assert tx_route.call_count == 0
            assert (await client.get("/accounts/link/status", params={"ref": ref})).json()[
                "data_status"
            ] == "PROCESSING"
            updated = {
                "event": "mono.events.account_updated",
                "event_id": "fake_updated",
                "data": {
                    "account": {
                        "_id": "fake_account",
                        "accountNumber": "0" * 10,
                        "currency": "NGN",
                        "balance": 10000000,
                        "type": "SAVINGS",
                        "institution": {
                            "name": "OPAY DIGITAL SERVICES LIMITED",
                            "bankCode": "00711",
                        },
                    },
                    "meta": {
                        "ref": ref,
                        "data_status": "AVAILABLE",
                        "retrieved_data": ["balance", "transactions"],
                    },
                },
            }
            assert (
                await client.post("/webhooks/mono", json=updated, headers=headers)
            ).status_code == 200
            status = (await client.get("/accounts/link/status", params={"ref": ref})).json()
            assert status["data_status"] == "AVAILABLE" and status["account_id"]
            account_id = status["account_id"]
            assert tx_route.call_count == 1
            await client.post("/webhooks/mono", json=updated, headers=headers)
            assert tx_route.call_count == 1
            connected["event_id"] = "fake_late_connected"
            await client.post("/webhooks/mono", json=connected, headers=headers)
            assert (await client.get("/accounts/link/status", params={"ref": ref})).json()[
                "data_status"
            ] == "AVAILABLE"
            group = (await client.get("/accounts")).json()["groups"]["digital_bank_wallet"]
            assert group["count"] == 1 and group["accounts"][0]["sync_status"] == "ok"
            activity = (await client.get("/transactions", params={"type": "debit"})).json()
            assert activity[0]["category"] == "Food & Dining"
            assert activity[0]["raw_narration"] == transaction_data[0]["narration"]
            assert (
                await client.patch(
                    f"/transactions/{activity[0]['id']}/category",
                    json={"category": "Transport", "apply_to_future": True},
                )
            ).status_code == 200
            assert (await client.get("/analytics/spending")).json()["total_outflow_minor"] == 1000
            user_id = decode_access(tokens["access_token"])
            async with sessions() as db:
                await supplement(db, user_id)
                await db.commit()
            assert (await client.get("/budget/velocity")).json()["status"] == "on_track"
            assert len((await client.get("/assets")).json()) == 2
            assert len((await client.get("/obligations")).json()) == 1
            position = (await client.get("/net-position")).json()
            assert position["cash_minor"] == 10000000 and position["investments_minor"] == 20000000
            assert (await client.post(f"/accounts/{account_id}/refresh")).headers.get("Retry-After")
            assert (await client.post(f"/accounts/{account_id}/pause")).status_code == 200
            assert (await client.post(f"/accounts/{account_id}/refresh")).status_code == 409
            assert (await client.post(f"/accounts/{account_id}/resume")).status_code == 200
            async with sessions() as db:
                account = await db.get(Account, UUID(account_id))
                account.last_synced_at -= timedelta(minutes=6)
                await db.commit()
            respx.get(base + "/v2/accounts/fake_account/balance").mock(
                return_value=httpx.Response(
                    200,
                    headers={"x-job-status": "processing", "x-has-new-data": "false"},
                    json={"data": {"balance": 999, "currency": "NGN"}},
                )
            )
            processing = await client.post(f"/accounts/{account_id}/refresh")
            assert processing.status_code == 200 and processing.json()["status"] == "requested"
            assert processing.json()["cached_balance_minor"] == 10000000
            main._refresh_requests.clear()
            respx.get(base + "/v2/accounts/fake_account/balance").mock(
                return_value=httpx.Response(400)
            )
            refresh = await client.post(f"/accounts/{account_id}/refresh")
            assert refresh.status_code == 200 and refresh.json()["status"] == "delayed"
            assert refresh.json()["cached_balance_minor"] == 10000000
            # A family-less logout must not revoke another user's family-less token.
            async with sessions() as db:
                other = User(phone=None, email="other@example.com", created_at=now_utc())
                db.add(other)
                await db.flush()
                other_token = RefreshToken(
                    user_id=other.id,
                    token_hash=hash_secret("fake-other-token"),
                    family_id=None,
                    expires_at=now_utc() + timedelta(days=1),
                )
                db.add(other_token)
                await db.commit()
                other_id = other_token.id
            assert (
                await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
            ).status_code == 204
            assert (
                await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            ).status_code == 401
            async with sessions() as db:
                assert (await db.get(RefreshToken, other_id)).revoked_at is None
                assert len((await db.execute(select(Transaction))).scalars().all()) == 1
                assert all(
                    event.processing_status == "processed"
                    for event in (await db.execute(select(WebhookEvent))).scalars()
                )
            assert "fake_connect_key_for_demo_tests_123" not in caplog.text
            assert "654321" not in caplog.text
    finally:
        main.app.dependency_overrides.clear()
        main.get_rate_limiter.cache_clear()
        main._refresh_requests.clear()
        await engine.dispose()
