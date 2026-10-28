"""Completed deliveries dedupe; failed or abandoned work can be claimed again."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.clock import now_utc
from app.models import Base, WebhookEvent


@pytest.mark.asyncio
async def test_failed_webhook_can_retry_and_completed_delivery_is_not_reapplied(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        db.add(
            WebhookEvent(
                event_key="fake-event",
                event_name="mono.events.account_updated",
                received_at=now_utc(),
            )
        )
        await db.commit()
    monkeypatch.setattr(main, "SessionLocal", sessions)
    calls = []

    async def apply(_event):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("fake failure")

    monkeypatch.setattr(main, "apply_mono_event", apply)
    try:
        await main.process_mono_event({}, "fake-event")
        async with sessions() as db:
            row = (await db.execute(select(WebhookEvent))).scalar_one()
            assert row.processing_status == "failed" and row.processed_at is None
        await main.process_mono_event({}, "fake-event")
        await main.process_mono_event({}, "fake-event")
        assert len(calls) == 2
        async with sessions() as db:
            row = (await db.execute(select(WebhookEvent))).scalar_one()
            row.processing_status = "processing"
            row.processing_started_at = now_utc() - timedelta(minutes=3)
            await db.commit()
        await main.process_mono_event({}, "fake-event")
        assert len(calls) == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_delivery_cannot_claim_active_processing(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        db.add(
            WebhookEvent(
                event_key="concurrent",
                event_name="mono.events.account_updated",
                received_at=now_utc(),
            )
        )
        await db.commit()
    monkeypatch.setattr(main, "SessionLocal", sessions)
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def apply(_event):
        calls.append(True)
        started.set()
        await release.wait()

    monkeypatch.setattr(main, "apply_mono_event", apply)
    task = asyncio.create_task(main.process_mono_event({}, "concurrent"))
    try:
        await asyncio.wait_for(started.wait(), 2)
        await main.process_mono_event({}, "concurrent")
        assert len(calls) == 1
    finally:
        release.set()
        await task
        await engine.dispose()
