"""Phase 6 NET, SPD, BUD and OBL requirement coverage."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.ledger.obligations import obligation_lender, sync_detected_obligations
from app.models import (
    Account,
    AccountType,
    Base,
    Consent,
    Direction,
    Institution,
    ManualAsset,
    ManualAssetCategory,
    ManualAssetPlatform,
    Merchant,
    Obligation,
    ObligationPayment,
    ProviderLink,
    RecurringSeries,
    SeriesStatus,
    Transaction,
    UpdateCadence,
    User,
)

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_OBL_1_generic_loan_and_direct_debit_patterns_are_conservative():
    assert obligation_lender("monthly loan repayment acme") == (
        "monthly loan repayment acme",
        "loan",
    )
    assert obligation_lender("DIRECT DEBIT ACME") == ("DIRECT ACME", "direct_debit")
    assert obligation_lender("ordinary grocery purchase") is None


def test_NET_6_migration_0021_is_reversible():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Column, ForeignKey, MetaData, Table, Uuid, create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0021_phase6_money_views.py"
    spec = importlib.util.spec_from_file_location("phase6_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Uuid(), primary_key=True))
    Table(
        "user_settings",
        metadata,
        Column("user_id", Uuid(), ForeignKey("users.id"), primary_key=True),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "privacy_blur" in {
            item["name"] for item in inspect(connection).get_columns("user_settings")
        }
        migration.downgrade()
        assert "privacy_blur" not in {
            item["name"] for item in inspect(connection).get_columns("user_settings")
        }
    engine.dispose()


@pytest.mark.asyncio
async def test_NET_1_NET_3_NET_4_NET_6_SPD_1_BUD_1_OBL_2_money_view_api(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        user = User(created_at=NOW)
        institution = Institution(name="Fixture Bank", code="P6", savings_rate_bps=0)
        db.add_all((user, institution))
        await db.flush()
        accounts = []
        for index, paused in enumerate((False, True)):
            consent = Consent(
                user_id=user.id,
                institution=institution.name,
                scope="transactions:read balance:read",
                granted_at=NOW,
                expires_at=NOW + timedelta(days=30),
            )
            db.add(consent)
            await db.flush()
            account = Account(
                user_id=user.id,
                institution_id=institution.id,
                consent_id=consent.id,
                account_number_masked=f"****{index:04d}",
                type=AccountType.current,
                current_balance_minor=100_000 * (index + 1),
                sync_paused=paused,
            )
            db.add(account)
            await db.flush()
            db.add(
                ProviderLink(
                    user_id=user.id,
                    consent_id=consent.id,
                    provider="fixture",
                    provider_account_id_hash=uuid4().hex * 2,
                    status="connected",
                    created_at=NOW,
                )
            )
            accounts.append(account)
        db.add(
            ManualAsset(
                user_id=user.id,
                platform=ManualAssetPlatform.bamboo,
                category=ManualAssetCategory.us_equities,
                currency="USD",
                amount_minor=100,
                fx_rate_used=1_500_000_000,
                update_cadence=UpdateCadence.monthly,
                last_updated_at=NOW,
                next_reminder_at=NOW + timedelta(days=30),
            )
        )
        for index, merchant in enumerate(("Cafe Lagos", "Market")):
            db.add(
                Transaction(
                    account_id=accounts[0].id,
                    posted_at=NOW - timedelta(days=index),
                    amount_minor=1_000,
                    direction=Direction.debit,
                    narration_raw=merchant,
                    narration_clean=merchant,
                    decoded_merchant=merchant,
                    category="Food & Dining",
                    channel="POS",
                    dedupe_hash=uuid4().hex * 2,
                )
            )
        await db.commit()

    async def database():
        async with sessions() as db:
            yield db

    async def identity():
        return user

    async def current_rate(_db, _supplied):
        return 1_600_000_000, "fixture"

    monkeypatch.setattr(main, "get_usd_ngn_rate", current_rate)
    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[current_user] = identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            position = (await client.get("/net-position")).json()
            assert position["cash_minor"] == 300_000
            assert position["investments_minor"] == 160_000
            assert position["paused_accounts_included"] == 1
            assert len(position["breakdown"]) == 3
            assert position["fx_rate_warning"] is False
            merchant_rows = (await client.get("/transactions", params={"merchant": "cafe"})).json()
            assert len(merchant_rows) == 1 and merchant_rows[0]["decoded_merchant"] == "Cafe Lagos"
            effective = NOW - timedelta(days=1)
            budget = await client.put(
                "/budget",
                json={"monthly_limit_minor": 10_000, "effective_from": effective.isoformat()},
            )
            assert budget.status_code == 200
            assert budget.json()["effective_from"].startswith(effective.date().isoformat())
            assert (await client.get("/privacy-preferences")).json() == {"privacy_blur": False}
            assert (
                await client.put("/privacy-preferences", json={"privacy_blur": True})
            ).json() == {"privacy_blur": True}
            created = await client.post(
                "/obligations",
                json={
                    "lender_name": "Manual lender",
                    "kind": "loan",
                    "amount_minor": 25_000,
                    "cadence_days": 30,
                    "next_due_date": (NOW + timedelta(days=10)).date().isoformat(),
                    "account_id": str(accounts[0].id),
                },
            )
            obligation_id = created.json()["id"]
            reviewed = await client.patch(
                f"/obligations/{obligation_id}",
                json={"status": "confirmed", "amount_minor": 26_000},
            )
            assert reviewed.json()["status"] == "confirmed"
            assert reviewed.json()["amount_minor"] == 26_000
            assert (
                await client.patch(f"/obligations/{obligation_id}", json={"status": "dismissed"})
            ).status_code == 200
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_OBL_1_OBL_3_generic_detection_and_payment_history():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        user = User(created_at=NOW)
        institution = Institution(name="Fixture", code="OBL6", savings_rate_bps=0)
        db.add_all((user, institution))
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="Fixture",
            scope="transactions:read",
            granted_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        account = Account(
            user_id=user.id,
            institution_id=institution.id,
            consent_id=consent.id,
            account_number_masked="****0000",
            type=AccountType.current,
            current_balance_minor=0,
        )
        merchant = Merchant(
            canonical_name="DIRECT DEBIT ACME", category_default="Bills & Utilities"
        )
        db.add_all((account, merchant))
        await db.flush()
        db.add(
            RecurringSeries(
                user_id=user.id,
                account_id=account.id,
                merchant_id=merchant.id,
                cadence_days=30,
                typical_amount_minor=50_000,
                last_amount_minor=50_000,
                previous_amount_minor=50_000,
                cycles=4,
                first_seen_at=NOW - timedelta(days=90),
                last_seen_at=NOW,
                next_expected_at=NOW + timedelta(days=5),
                status=SeriesStatus.active,
                direction=Direction.debit,
            )
        )
        payment = Transaction(
            account_id=account.id,
            posted_at=NOW,
            amount_minor=50_000,
            direction=Direction.debit,
            narration_raw="DIRECT DEBIT ACME",
            narration_clean="DIRECT DEBIT ACME",
            decoded_merchant="DIRECT DEBIT ACME",
            category="Bills & Utilities",
            channel="OTHER",
            dedupe_hash=uuid4().hex * 2,
        )
        db.add(payment)
        await db.flush()
        assert await sync_detected_obligations(db, user.id) == 1
        await db.commit()
        obligation = (await db.scalars(select(Obligation))).one()
        assert obligation.kind == "direct_debit"
        assert obligation.confidence_bps == 8000
        assert obligation.next_due_date == (NOW + timedelta(days=5)).date()
        assert obligation.source == "detected"
        assert len((await db.scalars(select(ObligationPayment))).all()) == 1
    await engine.dispose()
