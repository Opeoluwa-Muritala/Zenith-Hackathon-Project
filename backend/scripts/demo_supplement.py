"""Add fictional finance records to one allowlisted demo user, without provider calls."""

import argparse
import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.assets.service import next_reminder
from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import (
    Budget,
    ManualAsset,
    ManualAssetCategory,
    ManualAssetPlatform,
    Obligation,
    UpdateCadence,
    User,
)


async def supplement(db, user_id: UUID) -> dict[str, int]:
    settings = get_settings()
    if not settings.demo_mode or settings.environment == "production":
        raise ValueError("Demo mode must be enabled outside production")
    user = await db.get(User, user_id)
    if user is None or not ({user.phone, user.email} & settings.demo_identity_allowlist):
        raise ValueError("User must be a configured demo identity")
    now = now_utc()
    created = {"budgets": 0, "assets": 0, "obligations": 0}
    if not (
        await db.execute(select(Budget.id).where(Budget.user_id == user_id).limit(1))
    ).scalar_one_or_none():
        db.add(Budget(user_id=user_id, monthly_limit_minor=20_000_000, effective_from=now))
        created["budgets"] = 1
    for currency, amount, category, fx_rate in (
        ("NGN", 5_000_000, ManualAssetCategory.mutual_funds, None),
        ("USD", 10_000, ManualAssetCategory.dollar_savings, 1_500_000_000),
    ):
        existing = (
            await db.execute(
                select(ManualAsset.id)
                .where(
                    ManualAsset.user_id == user_id,
                    ManualAsset.platform == ManualAssetPlatform.custom_cash_vault,
                    ManualAsset.category == category,
                    ManualAsset.currency == currency,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            ManualAsset(
                user_id=user_id,
                platform=ManualAssetPlatform.custom_cash_vault,
                category=category,
                currency=currency,
                amount_minor=amount,
                fx_rate_used=fx_rate,
                update_cadence=UpdateCadence.monthly,
                last_updated_at=now,
                next_reminder_at=next_reminder(now, UpdateCadence.monthly),
            )
        )
        created["assets"] += 1
    if not (
        await db.execute(
            select(Obligation.id)
            .where(
                Obligation.user_id == user_id,
                Obligation.lender_name == "Demo Loan",
                Obligation.source == "manual",
            )
            .limit(1)
        )
    ).scalar_one_or_none():
        db.add(
            Obligation(
                user_id=user_id,
                account_id=None,
                lender_name="Demo Loan",
                kind="loan",
                amount_minor=1_000_000,
                cadence_days=30,
                next_due_date=(now + timedelta(days=3)).date(),
                confidence_bps=10_000,
                status="upcoming",
                source="manual",
            )
        )
        created["obligations"] = 1
    await db.flush()
    return created


async def run(user_id: UUID):
    get_settings().validate_runtime()
    async with SessionLocal() as db:
        result = await supplement(db, user_id)
        await db.commit()
    print(result)
    print("USD fixture uses a fictional 1500 NGN/USD rate, not a market reference.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=UUID, required=True)
    asyncio.run(run(parser.parse_args().user_id))
