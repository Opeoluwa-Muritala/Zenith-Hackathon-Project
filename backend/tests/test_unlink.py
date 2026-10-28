"""Local account purge survives Mono failure and leaves an encrypted retry target."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.ledger import unlink as unlink_module
from app.ledger.service import ingest
from app.models import (
    Account,
    AccountType,
    Base,
    Consent,
    Institution,
    ProviderLink,
    Transaction,
    User,
)
from app.providers.base import ProviderTransaction, ProviderUnavailable


@pytest.mark.asyncio
async def test_account_unlink_purges_local_data_and_retries_remote(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime.now(UTC)
    async with sessions() as db:
        user = User(phone="+2348000000100", email=None, created_at=now)
        bank = Institution(name="Fake Bank", code="FAKE-UNLINK", savings_rate_bps=0)
        db.add_all([user, bank])
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="Fake Bank",
            scope="auth",
            granted_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        account = Account(
            user_id=user.id,
            institution_id=bank.id,
            consent_id=consent.id,
            account_number_masked="******1234",
            type=AccountType.current,
            currency="NGN",
            current_balance_minor=1000,
        )
        db.add(account)
        await db.flush()
        link = ProviderLink(
            user_id=user.id,
            consent_id=consent.id,
            provider="mono",
            provider_account_id="acc_fake_unlink",
            status="connected",
            created_at=now,
        )
        db.add(link)
        await ingest(
            db,
            account,
            [ProviderTransaction("fake_tx", now, 100, "debit", "POS FAKE", None, None)],
        )
        await db.commit()
        account_id, link_id = account.id, link.id

    async def db_override():
        async with sessions() as db:
            yield db

    async def user_override():
        return user

    class FailingMono:
        def __init__(self, *_args):
            pass

        async def unlink(self, _identifier):
            raise ProviderUnavailable("mock failure")

    class WorkingMono:
        def __init__(self, *_args):
            pass

        async def unlink(self, identifier):
            assert identifier == "acc_fake_unlink"

    main.app.dependency_overrides[get_db] = db_override
    main.app.dependency_overrides[current_user] = user_override
    monkeypatch.setattr(unlink_module, "MonoProvider", FailingMono)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            response = await client.post(f"/accounts/{account_id}/unlink")
            assert response.status_code == 200
            assert response.json()["status"] == "pending_unlink"
        async with sessions() as db:
            assert await db.get(Account, account_id) is None
            assert (await db.execute(select(Transaction))).scalar_one_or_none() is None
            link = await db.get(ProviderLink, link_id)
            assert link.provider_account_id_encrypted
            assert link.provider_account_id == "acc_fake_unlink"
            monkeypatch.setattr(unlink_module, "MonoProvider", WorkingMono)
            assert await unlink_module.retry_pending_link(db, link) is True
            await db.commit()
            assert link.status == "unlinked"
            assert link.provider_account_id_encrypted is None
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
