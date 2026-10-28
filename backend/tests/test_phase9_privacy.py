"""Phase 9 PRV requirement coverage."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.identity.otp import code_digest
from app.models import (
    Account,
    AccountType,
    Base,
    Channel,
    Consent,
    Direction,
    Institution,
    OtpCode,
    PendingUnlink,
    ProviderLink,
    SecurityAuditEvent,
    Transaction,
    User,
    WipeAudit,
)
from app.privacy.service import PURGE_USER_FOREIGN_KEYS

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_PRV_3_PRV_4_migration_0024_is_reversible():
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0024_phase9_privacy_wipe.py"
    spec = importlib.util.spec_from_file_location("phase9_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {"pending_unlinks", "wipe_audits"} <= set(inspect(connection).get_table_names())
        migration.downgrade()
        assert "pending_unlinks" not in inspect(connection).get_table_names()
    engine.dispose()


def test_PRV_3_new_user_foreign_key_requires_a_purge_decision():
    actual = {
        f"{table.name}.{foreign_key.parent.name}"
        for table in Base.metadata.tables.values()
        for foreign_key in table.foreign_keys
        if foreign_key.column.table.name == "users"
    }
    assert actual == PURGE_USER_FOREIGN_KEYS


@pytest.mark.asyncio
async def test_PRV_1_PRV_3_PRV_4_active_consents_and_complete_wipe(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    otp = "123456"
    salt = "a" * 32
    async with sessions() as db:
        user = User(phone="+2348000000099", created_at=NOW)
        institution = Institution(name="Fixture Bank", code="PRV9", savings_rate_bps=0)
        db.add_all((user, institution))
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="Fixture Bank",
            scope="accounts:read transactions:read",
            granted_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        link = ProviderLink(
            user_id=user.id,
            consent_id=consent.id,
            provider="mono",
            status="connected",
            data_status="AVAILABLE",
            created_at=NOW,
        )
        link.provider_account_id = "mono-test-account"
        db.add(link)
        await db.flush()
        account = Account(
            user_id=user.id,
            institution_id=institution.id,
            consent_id=consent.id,
            account_number_masked="****0099",
            type=AccountType.current,
            current_balance_minor=50_000,
        )
        db.add(account)
        await db.flush()
        db.add_all(
            (
                Transaction(
                    account_id=account.id,
                    posted_at=NOW,
                    amount_minor=1_000,
                    direction=Direction.debit,
                    narration_raw="TEST PURCHASE",
                    narration_clean="TEST PURCHASE",
                    category="Uncategorised",
                    channel=Channel.NIP,
                    dedupe_hash="d" * 64,
                ),
                OtpCode(
                    identifier=user.phone,
                    code_hash=code_digest(user.phone, otp, salt),
                    salt=salt,
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    created_at=NOW,
                ),
                SecurityAuditEvent(
                    user_id=user.id,
                    event="link.created",
                    subject_hash="e" * 64,
                    occurred_at=NOW,
                ),
            )
        )
        await db.commit()

    async def database():
        async with sessions() as db:
            yield db

    async def identity():
        return user

    async def unavailable_unlink(self, identifier):
        from app.providers.base import ProviderError

        raise ProviderError("fixture unavailable")

    monkeypatch.setattr("app.privacy.service.MonoProvider.unlink", unavailable_unlink)
    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[current_user] = identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            inventory = await client.get("/privacy/consents")
            assert inventory.status_code == 200
            assert inventory.json()[0] == {
                "consent_id": str(consent.id),
                "link_id": str(link.id),
                "institution": "Fixture Bank",
                "linked_at": "2026-10-28T12:00:00",
                "data_status": "AVAILABLE",
                "scope": "accounts:read transactions:read",
                "read_only": True,
            }
            assert (await client.post("/privacy/wipe", json={"otp": "000000"})).status_code == 401
            wiped = await client.post("/privacy/wipe", json={"otp": otp})
            assert wiped.status_code == 200, wiped.text
            assert wiped.json()["deleted"] == {
                "accounts": 1,
                "transactions": 1,
                "manual_assets": 0,
            }
            assert wiped.json()["unlink_pending"] is True
    finally:
        main.app.dependency_overrides.clear()

    async with sessions() as db:
        assert await db.get(User, user.id) is None
        assert (await db.scalars(select(OtpCode))).all() == []
        assert (await db.scalars(select(SecurityAuditEvent))).all() == []
        audit = (await db.scalars(select(WipeAudit))).one()
        assert audit.user_hash != str(user.id)
        queued = (await db.scalars(select(PendingUnlink))).one()
        assert queued.completed_at is None and queued.attempts == 1
        assert "mono-test-account" not in queued.provider_account_id_encrypted
    await engine.dispose()
