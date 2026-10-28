"""Rerunning fixture preparation preserves edits and does not touch linked accounts."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.clock import now_utc
from app.core.config import get_settings
from app.models import Base, Budget, ManualAsset, User
from scripts.demo_supplement import supplement


@pytest.mark.asyncio
async def test_supplement_is_allowlisted_and_preserves_edits(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    monkeypatch.setattr(get_settings(), "demo_identifiers", "user@example.com")
    async with sessions() as db:
        user = User(phone=None, email="user@example.com", created_at=now_utc())
        other = User(phone=None, email="other@example.com", created_at=now_utc())
        db.add_all([user, other])
        await db.flush()
        with pytest.raises(ValueError, match="demo identity"):
            await supplement(db, other.id)
        assert await supplement(db, user.id) == {"budgets": 1, "assets": 2, "obligations": 1}
        budget = (await db.execute(select(Budget))).scalar_one()
        budget.monthly_limit_minor = 12300
        asset = (
            await db.execute(select(ManualAsset).where(ManualAsset.currency == "NGN"))
        ).scalar_one()
        asset.amount_minor = 45600
        await db.commit()
        assert await supplement(db, user.id) == {"budgets": 0, "assets": 0, "obligations": 0}
        assert budget.monthly_limit_minor == 12300 and asset.amount_minor == 45600
    await engine.dispose()
