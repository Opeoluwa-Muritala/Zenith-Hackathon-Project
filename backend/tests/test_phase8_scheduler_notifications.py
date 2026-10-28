"""Phase 8 NTF and scheduler requirement coverage."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.encryption import encrypt_field, hash_field
from app.models import (
    Base,
    DeviceToken,
    JobRun,
    NotificationLog,
    OtpCode,
    User,
)
from app.notifications.push import PushResult
from app.notifications.service import send_notification
from app.scheduler import lock
from app.scheduler.jobs import cleanup_job

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


class FakePushProvider:
    def __init__(self, results: list[PushResult]):
        self.results = results
        self.tokens: list[str] = []

    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult:
        self.tokens.append(token)
        return self.results.pop(0)


def test_NTF_3_migration_0023_is_reversible():
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Boolean, Column, MetaData, String, Table, Uuid, create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0023_phase8_scheduler_notifications.py"
    spec = importlib.util.spec_from_file_location("phase8_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Uuid(), primary_key=True))
    Table(
        "device_tokens",
        metadata,
        Column("id", Uuid(), primary_key=True),
        Column("user_id", Uuid()),
        Column("platform", String(20)),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(inspect(connection).get_table_names())
        assert {"notification_logs", "job_runs"} <= tables
        columns = {item["name"]: item for item in inspect(connection).get_columns("device_tokens")}
        assert isinstance(columns["is_valid"]["type"], Boolean)
        migration.downgrade()
        assert "notification_logs" not in inspect(connection).get_table_names()
        assert "is_valid" not in {
            item["name"] for item in inspect(connection).get_columns("device_tokens")
        }
    engine.dispose()


@pytest.mark.asyncio
async def test_NTF_1_NTF_3_delivery_is_encrypted_deduplicated_and_invalidated():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sample_device_value = "test-device-value-never-persist-raw"
    async with sessions() as db:
        user = User(phone="+2348000000081", created_at=NOW)
        db.add(user)
        await db.flush()
        device = DeviceToken(
            user_id=user.id,
            token_encrypted=encrypt_field(sample_device_value),
            token_hash=hash_field(sample_device_value),
            platform="android",
            last_seen_at=NOW,
        )
        db.add(device)
        await db.commit()

        sent_provider = FakePushProvider(["sent"])
        assert (
            await send_notification(
                db,
                sent_provider,
                user_id=user.id,
                event_key="money-event:credit:1",
                kind="money_event",
                title="Money received",
                body="A credit was detected.",
            )
            == 1
        )
        assert (
            await send_notification(
                db,
                sent_provider,
                user_id=user.id,
                event_key="money-event:credit:1",
                kind="money_event",
                title="Money received",
                body="A credit was detected.",
            )
            == 0
        )
        assert sent_provider.tokens == [sample_device_value]

        invalid_provider = FakePushProvider(["unregistered"])
        await send_notification(
            db,
            invalid_provider,
            user_id=user.id,
            event_key="money-event:debit:2",
            kind="money_event",
            title="Money spent",
            body="A debit was detected.",
        )
        await db.refresh(device)
        assert device.is_valid is False and device.invalidated_at is not None
        logs = (await db.scalars(select(NotificationLog))).all()
        assert [item.status for item in logs] == ["sent", "unregistered"]
        assert sample_device_value not in " ".join(item.event_key for item in logs)
    await engine.dispose()


@pytest.mark.asyncio
async def test_NTF_3_job_lock_runs_each_scheduled_job_once(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(lock, "SessionLocal", sessions)
    calls = 0

    async def callback() -> None:
        nonlocal calls
        calls += 1

    assert await lock.run_locked("cleanup", NOW, callback) is True
    assert await lock.run_locked("cleanup", NOW, callback) is False
    assert calls == 1
    async with sessions() as db:
        row = (await db.scalars(select(JobRun))).one()
        assert row.status == "completed" and row.completed_at is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_NTF_3_cleanup_job_removes_expired_records(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr("app.scheduler.jobs.SessionLocal", sessions)
    async with sessions() as db:
        db.add_all(
            (
                OtpCode(
                    identifier="expired@example.com",
                    code_hash="a" * 64,
                    salt="b" * 32,
                    expires_at=NOW - timedelta(seconds=1),
                    created_at=NOW - timedelta(minutes=6),
                ),
                OtpCode(
                    identifier="active@example.com",
                    code_hash="c" * 64,
                    salt="d" * 32,
                    expires_at=NOW + timedelta(minutes=5),
                    created_at=NOW,
                ),
            )
        )
        await db.commit()
    await cleanup_job(NOW)
    async with sessions() as db:
        remaining = (await db.scalars(select(OtpCode.identifier))).all()
        assert remaining == ["active@example.com"]
    await engine.dispose()


def test_NTF_3_missing_fcm_credentials_warns_once(monkeypatch, caplog):
    from app.notifications import push

    monkeypatch.setattr(push, "_disabled_warning_emitted", False)
    monkeypatch.setattr(push.get_settings(), "fcm_credentials_json", "")
    push.push_provider()
    push.push_provider()
    assert caplog.messages.count("push_disabled_missing_credentials") == 1
