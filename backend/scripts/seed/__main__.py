"""Load six-month provider fixtures and run the insight pipeline."""

import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import now_utc
from app.core.db import SessionLocal
from app.insights.runner import run_for_user
from app.ledger.recurring import rebuild_account
from app.ledger.service import ingest
from app.models import (
    Account,
    AccountType,
    Consent,
    ConsentAudit,
    Institution,
    ProviderLink,
    User,
    UserSettings,
)
from app.providers.mock import MockAggregatorProvider

PERSONAS = (
    ("salaried", "+2348000000001", 25_000_000, 180_000_000),
    ("freelancer", "+2348000000002", 1_000_000, 0),
    ("student", "+2348000000003", 150_000, 0),
)


async def seed():
    """Insert fake users, accounts and consented provider transactions once."""
    now = now_utc()
    async with SessionLocal() as db:
        for code, name, rate in (
            ("DEMO-A", "Demo Cedar Bank", 100),
            ("DEMO-B", "Demo Lagoon Bank", 200),
            ("DEMO-C", "Demo Campus Wallet", 0),
        ):
            if not (
                await db.execute(select(Institution.id).where(Institution.code == code))
            ).scalar_one_or_none():
                db.add(Institution(code=code, name=name, logo_url=None, savings_rate_bps=rate))
        await db.flush()
        institutions = {
            item.code: item for item in (await db.execute(select(Institution))).scalars()
        }
        for persona, phone, balance, savings in PERSONAS:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
            if user is None:
                user = User(
                    phone=phone,
                    email=f"{persona}@example.invalid",
                    bvn_hash=None,
                    bvn_last4=None,
                    created_at=now,
                )
                db.add(user)
                await db.flush()
            if await db.get(UserSettings, user.id) is None:
                db.add(
                    UserSettings(
                        user_id=user.id,
                        safe_buffer_minor=500_000,
                        payday_hint=25,
                        discretionary_categories=["food", "shopping", "entertainment", "transport"],
                        nominal_tbill_rate_bps=1500,
                    )
                )
            code = "DEMO-C" if persona == "student" else "DEMO-A"
            consent = (
                await db.execute(
                    select(Consent).where(
                        Consent.user_id == user.id,
                        Consent.institution == code,
                        Consent.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if consent is None:
                consent = Consent(
                    user_id=user.id,
                    institution=code,
                    scope="transactions,balance",
                    granted_at=now,
                    expires_at=now + timedelta(days=365),
                    revoked_at=None,
                )
                db.add(consent)
                await db.flush()
                db.add(ConsentAudit(consent_id=consent.id, event="granted", actor="seed", at=now))
            account = (
                await db.execute(
                    select(Account).where(
                        Account.consent_id == consent.id, Account.user_id == user.id
                    )
                )
            ).scalar_one_or_none()
            if account is None:
                account = Account(
                    user_id=user.id,
                    consent_id=consent.id,
                    institution_id=institutions[code].id,
                    account_number_masked="******0001",
                    type=AccountType.wallet if persona == "student" else AccountType.current,
                    currency="NGN",
                    current_balance_minor=balance,
                    last_synced_at=None,
                )
                db.add(account)
                await db.flush()
                db.add(
                    ProviderLink(
                        user_id=user.id,
                        consent_id=consent.id,
                        provider="mock",
                        provider_account_id=f"{persona}:{account.id}",
                        status="connected",
                        data_status="AVAILABLE",
                        created_at=now,
                        last_webhook_at=None,
                    )
                )
            rows = await MockAggregatorProvider().transactions(
                f"{persona}:{account.id}", now - timedelta(days=190), now
            )
            await ingest(db, account, rows)
            await db.flush()
            await rebuild_account(db, account.id, user.id, now)
            await db.flush()
            if savings:
                other = (
                    await db.execute(
                        select(Consent).where(
                            Consent.user_id == user.id,
                            Consent.institution == "DEMO-B",
                            Consent.revoked_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()
                if other is None:
                    other = Consent(
                        user_id=user.id,
                        institution="DEMO-B",
                        scope="transactions,balance",
                        granted_at=now,
                        expires_at=now + timedelta(days=365),
                        revoked_at=None,
                    )
                    db.add(other)
                    await db.flush()
                    db.add(ConsentAudit(consent_id=other.id, event="granted", actor="seed", at=now))
                    idle = Account(
                        user_id=user.id,
                        consent_id=other.id,
                        institution_id=institutions["DEMO-B"].id,
                        account_number_masked="******0002",
                        type=AccountType.savings,
                        currency="NGN",
                        current_balance_minor=savings,
                        last_synced_at=None,
                    )
                    db.add(idle)
                    await db.flush()
                    db.add(
                        ProviderLink(
                            user_id=user.id,
                            consent_id=other.id,
                            provider="mock",
                            provider_account_id=f"idle:{idle.id}",
                            status="connected",
                            data_status="AVAILABLE",
                            created_at=now,
                            last_webhook_at=None,
                        )
                    )
            await run_for_user(db, user.id, now)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
