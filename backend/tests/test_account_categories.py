"""Account categories have explicit provenance and currency-safe totals."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.ledger.account_categories import category_for_institution
from app.models import Account, AccountCategory, AccountType, Base, Consent, Institution, User


def test_institution_category_mapping_is_conservative():
    assert category_for_institution("", "OPay") == (AccountCategory.digital_bank_wallet, False)
    assert category_for_institution("unknown", "Unlisted Institution") == (
        AccountCategory.commercial_bank,
        True,
    )


@pytest.mark.asyncio
async def test_accounts_are_grouped_without_mixing_currencies():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime.now(UTC)
    async with sessions() as db:
        user = User(phone="+2348000000101", email=None, created_at=now)
        bank = Institution(name="OPay", code="OPAY", savings_rate_bps=0)
        db.add_all([user, bank])
        await db.flush()
        consent = Consent(
            user_id=user.id,
            institution="OPay",
            scope="auth",
            granted_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        for currency, balance in [("NGN", 100), ("USD", 200)]:
            db.add(
                Account(
                    user_id=user.id,
                    institution_id=bank.id,
                    consent_id=consent.id,
                    account_number_masked="******1234",
                    type=AccountType.current,
                    currency=currency,
                    current_balance_minor=balance,
                    category=AccountCategory.digital_bank_wallet,
                )
            )
        await db.commit()

    async def db_override():
        async with sessions() as db:
            yield db

    async def user_override():
        return user

    main.app.dependency_overrides[get_db] = db_override
    main.app.dependency_overrides[current_user] = user_override
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            response = await client.get("/accounts")
        assert response.status_code == 200
        group = response.json()["groups"]["digital_bank_wallet"]
        assert group["count"] == 2
        assert group["totals_minor_by_currency"] == {"NGN": 100, "USD": 200}
        assert all(not row["category_unmapped"] for row in group["accounts"])
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
