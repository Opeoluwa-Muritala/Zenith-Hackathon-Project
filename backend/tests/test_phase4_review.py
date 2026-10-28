"""Phase 4 operator boundaries and owner-scoped review lifecycle."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.ledger.review import promote_reviewed_rule
from app.models import (
    Account,
    AccountType,
    Base,
    CategoryRule,
    ClassificationCorrection,
    Consent,
    Institution,
    ReviewedGlobalRule,
    Transaction,
    TransferSuggestion,
    User,
)


@pytest.mark.asyncio
async def test_NDL_8_review_requires_independent_users_and_stores_only_hash():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        user = uuid4()
        for _ in range(3):
            db.add(
                ClassificationCorrection(
                    user_id=user,
                    counterparty_key="shop",
                    category="Shopping & Transfers",
                    confirmed=True,
                    created_at=datetime.now(UTC),
                )
            )
        await db.flush()
        with pytest.raises(ValueError, match="independent"):
            await promote_reviewed_rule(db, "shop", "Shopping & Transfers")
        db.add(
            ClassificationCorrection(
                user_id=uuid4(),
                counterparty_key="shop",
                category="Shopping & Transfers",
                confirmed=True,
                created_at=datetime.now(UTC),
            )
        )
        await db.flush()
        result = await promote_reviewed_rule(db, "shop", "Shopping & Transfers")
        assert len(result.narration_hash) == 64
        assert result.category == "Shopping & Transfers"
        assert (await db.scalars(select(ReviewedGlobalRule))).one() == result
    await engine.dispose()


def test_NDL_8_migration_0019_upgrade_and_downgrade():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0019_phase4_review.py"
    spec = importlib.util.spec_from_file_location("phase4_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "reviewed_global_rules" in inspect(connection).get_table_names()
        migration.downgrade()
        assert "transfer_suggestions" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_NDL_7_NDL_8_STM_2_ingestion_fallback_override_and_cross_source(monkeypatch):
    from datetime import timedelta

    from app.ledger import classifier
    from app.ledger.classifier import CachedClassifier, Classification
    from app.ledger.service import ingest
    from app.providers.base import ProviderTransaction

    class Model:
        async def classify(self, narration):
            return Classification(
                merchant="Example Shop", category="Shopping & Transfers", confidence=0.8
            )

    monkeypatch.setattr(classifier, "default_classifier", CachedClassifier(Model()))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        now = datetime.now(UTC)
        user = User(created_at=now)
        bank = Institution(name="Fixture", code="TEST", savings_rate_bps=0)
        db.add_all([user, bank])
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="TEST",
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
            account_number_masked="0000",
            type=AccountType.current,
            current_balance_minor=0,
        )
        db.add(account)
        await db.flush()
        row = ProviderTransaction("mono-1", now, 100, "debit", "NIP/EXAMPLE SHOP", None, None)
        assert await ingest(db, account, [row]) == 1
        tx = (await db.scalars(select(Transaction))).one()
        assert tx.classification_method == "model"
        tx.category, tx.classification_method = "Transport", "manual"
        upload = ProviderTransaction(
            "csv-999", now, 100, "debit", row.narration, None, None, "upload"
        )
        assert await ingest(db, account, [upload]) == 0
        assert tx.category == "Transport"
        db.add(
            CategoryRule(
                user_id=user.id,
                counterparty_key="example shop",
                category="Transport",
                created_at=now,
            )
        )
        await db.flush()
        next_row = ProviderTransaction(
            "mono-2", now + timedelta(days=1), 100, "debit", row.narration, None, None
        )
        assert await ingest(db, account, [next_row]) == 1
        transactions = (await db.scalars(select(Transaction))).all()
        assert all(item.category == "Transport" for item in transactions)
        assert transactions[-1].classification_method == "user_rule"
        # A second identical charge in the upload must survive one cross-source match.
        second_upload = ProviderTransaction(
            "csv-1000", now, 100, "debit", row.narration, None, None, "upload"
        )
        assert await ingest(db, account, [upload, second_upload]) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_NDL_5_NDL_6_API_confirmation_dismissal_and_owner_isolation():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user = User(id=uuid4(), created_at=datetime.now(UTC))
    async with sessions() as db:
        suggestion = TransferSuggestion(
            user_id=user.id,
            counterparty_key="person",
            kind="family",
            status="pending",
            created_at=datetime.now(UTC),
        )
        foreign = TransferSuggestion(
            user_id=uuid4(),
            counterparty_key="other",
            kind="ajo",
            status="pending",
            created_at=datetime.now(UTC),
        )
        db.add_all([suggestion, foreign])
        await db.commit()
        own_id, foreign_id = suggestion.id, foreign.id

    async def database():
        async with sessions() as db:
            yield db

    async def identity():
        return user

    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[current_user] = identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            assert len((await client.get("/transfer-suggestions")).json()) == 1
            assert (
                await client.post(f"/transfer-suggestions/{foreign_id}/confirm")
            ).status_code == 404
            response = await client.post(f"/transfer-suggestions/{own_id}/confirm")
            assert response.json()["status"] == "confirmed"
            assert (await client.post(f"/transfer-suggestions/{own_id}/confirm")).status_code == 200
            async with sessions() as db:
                assert len((await db.scalars(select(CategoryRule))).all()) == 1
            response = await client.post(f"/transfer-suggestions/{own_id}/dismiss")
            assert response.json()["status"] == "dismissed"
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
