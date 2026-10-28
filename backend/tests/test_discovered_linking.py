"""Mono coverage mapping and hosted Link payloads without network calls."""

import json
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.models import (
    Base,
    Consent,
    DiscoveredAccount,
    DiscoveredAccountStatus,
    ProviderLink,
    User,
)
from app.providers.mono import MonoProvider


@pytest.mark.asyncio
async def test_institution_mapping_requires_unique_exact_code_and_auth_method(monkeypatch):
    row = DiscoveredAccount(user_id=uuid4(), bank_code="058", nip_code="000013")
    monkeypatch.setattr(
        main,
        "_institution_coverage",
        (
            time.monotonic() + 100,
            [
                {
                    "_id": "mono_bank_fake",
                    "bank_code": "058",
                    "auth_methods": [{"type": "internet_banking"}],
                }
            ],
        ),
    )
    assert await main.resolve_institution(row) == {
        "id": "mono_bank_fake",
        "auth_method": "internet_banking",
    }
    row.bank_code = "999"
    row.nip_code = "999999"
    assert await main.resolve_institution(row) is None


@pytest.mark.asyncio
@respx.mock
async def test_initiate_link_omits_unmapped_institution_and_match():
    route = respx.post("https://api.withmono.com/v2/accounts/initiate").mock(
        return_value=httpx.Response(200, json={"data": {"mono_url": "https://link.mono.co/fake"}})
    )
    provider = MonoProvider("test_sk_x")
    url = await provider.initiate("Fake User", "user@example.com", "ref_fake", "https://app.test")
    assert url == "https://link.mono.co/fake"
    payload = json.loads(route.calls.last.request.content)
    assert payload["scope"] == "auth"
    assert payload["meta"]["ref"] == "ref_fake"
    assert "institution" not in payload
    assert "check_account_match" not in payload
    await provider.initiate(
        "Fake User",
        "user@example.com",
        "ref_fake_2",
        "https://app.test",
        institution={"id": "mono_bank_fake", "auth_method": "internet_banking"},
    )
    payload = json.loads(route.calls.last.request.content)
    assert payload["institution"] == {
        "id": "mono_bank_fake",
        "auth_method": "internet_banking",
    }
    assert "check_account_match" not in payload


@pytest.mark.asyncio
async def test_connected_webhook_marks_discovery_linked_without_fetching_data(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime.now(UTC)
    async with sessions() as db:
        user = User(phone="+2348000000030", email=None, created_at=now)
        db.add(user)
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="Fake Bank",
            scope="auth",
            granted_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=None,
        )
        db.add(consent)
        await db.flush()
        link = ProviderLink(
            user_id=user.id,
            consent_id=consent.id,
            provider="mono",
            status="pending",
            created_at=now,
        )
        db.add(link)
        await db.flush()
        row = DiscoveredAccount(
            user_id=user.id,
            provider="mono",
            account_name="Fake User",
            account_designation="personal",
            bank_code="058",
            institution_name="Fake Bank",
            account_type="savings",
            account_number_encrypted="fake_encrypted_value",
            account_number_last4="1234",
            account_number_hash="fake_hash",
            status=DiscoveredAccountStatus.discovered,
            discovered_at=now,
            link_ref=str(link.id),
        )
        db.add(row)
        await db.commit()
        link_id, row_id = link.id, row.id

    class NoDataProvider:
        async def details(self, *_args, **_kwargs):
            raise AssertionError("Data must not be fetched during processing")

        async def transactions(self, *_args, **_kwargs):
            raise AssertionError("Data must not be fetched during processing")

    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(main, "provider", lambda: NoDataProvider())
    try:
        await main.process_mono_event(
            {
                "event": "mono.events.account_connected",
                "data": {
                    "id": "acc_fake_30",
                    "meta": {"ref": str(link_id), "data_status": "PROCESSING"},
                },
            }
        )
        async with sessions() as db:
            linked = await db.get(ProviderLink, link_id)
            discovered = await db.get(DiscoveredAccount, row_id)
            assert linked.data_status == "PROCESSING"
            assert linked.provider_account_id == "acc_fake_30"
            assert discovered.status == DiscoveredAccountStatus.linked
    finally:
        await engine.dispose()
