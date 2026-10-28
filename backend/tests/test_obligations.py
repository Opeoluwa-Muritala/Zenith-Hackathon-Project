"""Recurring lender debits become one obligation with deduplicated payment history."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ledger.obligations import sync_detected_obligations
from app.ledger.recurring import rebuild_account
from app.ledger.service import ingest
from app.models import (
    Account,
    AccountType,
    Base,
    Consent,
    Institution,
    Obligation,
    ObligationPayment,
    User,
)
from app.providers.base import ProviderTransaction


@pytest.mark.asyncio
async def test_recurring_lender_obligation_and_payment_matching_are_idempotent():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime(2026, 10, 15, tzinfo=UTC)
    async with sessions() as db:
        user = User(phone="+2348000000070", email=None, created_at=now)
        bank = Institution(name="Fake Bank", code="TEST-OBL", savings_rate_bps=0)
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
            current_balance_minor=100_000,
        )
        db.add(account)
        await db.flush()
        rows = [
            ProviderTransaction(
                f"fake_{index}",
                now - timedelta(days=90 - index * 30),
                5000,
                "debit",
                "NIP FAIRMoney repayment",
                None,
                None,
            )
            for index in range(3)
        ]
        assert await ingest(db, account, rows) == 3
        await db.flush()
        assert await rebuild_account(db, account.id, user.id, now) == 1
        await db.flush()
        assert await sync_detected_obligations(db, user.id) == 1
        await db.flush()
        obligation = (await db.execute(select(Obligation))).scalar_one()
        assert obligation.lender_name == "FairMoney"
        assert obligation.amount_minor == 5000
        assert (await db.execute(select(func.count(ObligationPayment.id)))).scalar_one() == 3
        assert await sync_detected_obligations(db, user.id) == 0
        await db.flush()
        assert (await db.execute(select(func.count(ObligationPayment.id)))).scalar_one() == 3
    await engine.dispose()
