"""Bounded, idempotent scheduled financial-data and notification jobs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.assets.service import next_reminder
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.identity.otp import cleanup_expired_inbox
from app.insights.detectors.velocity_warning import projected_month_end_spend
from app.ledger.service import active_accounts, as_utc
from app.ledger.unlink import retry_pending_link
from app.models import (
    Account,
    Budget,
    BvnLookupSession,
    Consent,
    Direction,
    JobRun,
    ManualAsset,
    NotificationLog,
    NotificationPreference,
    Obligation,
    OtpCode,
    ProviderCallLog,
    ProviderLink,
    SyncStatus,
    Transaction,
)
from app.notifications.push import PushProvider
from app.notifications.service import send_notification


async def account_sync_job(now: datetime, provider: PushProvider) -> None:
    """One scheduled read per connected account; provider adapters cap their own retries."""
    from app.main import sync_owned_account

    async with SessionLocal() as db:
        pairs = (
            await db.execute(
                select(Account, ProviderLink)
                .join(Consent, Account.consent_id == Consent.id)
                .join(ProviderLink, ProviderLink.consent_id == Account.consent_id)
                .where(
                    Account.sync_paused.is_(False),
                    ProviderLink.status == "connected",
                    Consent.revoked_at.is_(None),
                    Consent.expires_at > now,
                )
            )
        ).all()
        for account, link in pairs:
            call = ProviderCallLog(
                user_id=account.user_id,
                provider=link.provider,
                operation="scheduled_sync",
                account_id=account.id,
                requested_at=now,
                outcome="requested",
            )
            db.add(call)
            await db.flush()
            try:
                imported = await sync_owned_account(db, account, link, now)
                call.outcome = "success"
                account.sync_status = SyncStatus.ok
                if imported:
                    await send_notification(
                        db,
                        provider,
                        user_id=account.user_id,
                        event_key=f"account-activity:{account.id}:{now.isoformat()}",
                        kind="money_event",
                        title="New account activity",
                        body=f"Fetch found {imported} new transaction(s) in your latest sync.",
                        data={"account_id": str(account.id)},
                    )
            except HTTPException:
                call.outcome = "failed"
                account.sync_status = SyncStatus.delayed
            await db.commit()


async def stale_marking_job(now: datetime) -> None:
    cutoff = now - timedelta(minutes=get_settings().balance_stale_minutes)
    async with SessionLocal() as db:
        accounts = (
            await db.scalars(
                select(Account)
                .join(ProviderLink, ProviderLink.consent_id == Account.consent_id)
                .where(
                    ProviderLink.status == "connected",
                    Account.sync_paused.is_(False),
                )
            )
        ).all()
        for account in accounts:
            synced_at = as_utc(account.balance_synced_at)
            if synced_at is None or synced_at <= cutoff:
                account.sync_status = SyncStatus.delayed
        await db.commit()


async def unlink_retry_job(now: datetime) -> None:
    async with SessionLocal() as db:
        links = (
            await db.scalars(select(ProviderLink).where(ProviderLink.status == "pending_unlink"))
        ).all()
        for link in links:
            await retry_pending_link(db, link)
            await db.commit()


async def asset_reminder_job(now: datetime, provider: PushProvider) -> None:
    async with SessionLocal() as db:
        assets = (
            await db.scalars(select(ManualAsset).where(ManualAsset.next_reminder_at <= now))
        ).all()
        for asset in assets:
            reminder_at = asset.next_reminder_at
            if reminder_at is None:
                continue
            preference = await db.get(NotificationPreference, asset.user_id)
            if preference and not preference.investment_update_prompts:
                continue
            sent = await send_notification(
                db,
                provider,
                user_id=asset.user_id,
                event_key=f"asset:{asset.id}:{reminder_at.date().isoformat()}",
                kind="investment_update",
                title="Update an investment value",
                body="Review this manually tracked asset so your net position stays current.",
                data={"asset_id": str(asset.id)},
            )
            if sent:
                asset.next_reminder_at = next_reminder(now, asset.update_cadence)
                await db.commit()


async def obligation_reminder_job(now: datetime, provider: PushProvider) -> None:
    async with SessionLocal() as db:
        obligations = (
            await db.scalars(
                select(Obligation).where(Obligation.status.in_(("upcoming", "confirmed")))
            )
        ).all()
        for obligation in obligations:
            days = (obligation.next_due_date - now.date()).days
            if days not in {1, 3}:
                continue
            preference = await db.get(NotificationPreference, obligation.user_id)
            if preference and not preference.loan_repayment_reminders:
                continue
            await send_notification(
                db,
                provider,
                user_id=obligation.user_id,
                event_key=f"obligation:{obligation.id}:{obligation.next_due_date}:{days}",
                kind="repayment_due",
                title="Repayment due soon",
                body=(
                    f"A repayment of NGN {obligation.amount_minor / 100:,.2f} "
                    f"is due in {days} day(s)."
                ),
                data={"obligation_id": str(obligation.id)},
            )


async def overspending_alert_job(now: datetime, provider: PushProvider) -> None:
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    async with SessionLocal() as db:
        budgets = (
            await db.scalars(
                select(Budget)
                .where(Budget.effective_from <= now)
                .order_by(Budget.user_id, Budget.effective_from.desc())
            )
        ).all()
        current: dict[UUID, Budget] = {}
        for budget in budgets:
            current.setdefault(budget.user_id, budget)
        for user_id, budget in current.items():
            preference = await db.get(NotificationPreference, user_id)
            if preference and not preference.overspending_alerts:
                continue
            transactions = (
                await db.scalars(
                    select(Transaction).where(
                        Transaction.account_id.in_(active_accounts(user_id, now)),
                        Transaction.direction == Direction.debit,
                        Transaction.posted_at >= month_start,
                        Transaction.posted_at <= now,
                    )
                )
            ).all()
            spent = sum(item.amount_minor for item in transactions)
            projected = projected_month_end_spend(spent, now)
            status = (
                "exceeded"
                if spent > budget.monthly_limit_minor
                else ("warning" if projected > budget.monthly_limit_minor else "on_track")
            )
            if status == "on_track":
                continue
            await send_notification(
                db,
                provider,
                user_id=user_id,
                event_key=f"budget:{now.year}-{now.month:02d}:{status}",
                kind="overspending",
                title="Budget needs attention",
                body=f"Monthly spending is {status}; review your budget and recent transactions.",
                data={"status": status},
            )


async def cleanup_job(now: datetime) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(BvnLookupSession).where(BvnLookupSession.expires_at <= now))
        await db.execute(delete(OtpCode).where(OtpCode.expires_at <= now))
        await db.execute(
            delete(NotificationLog).where(
                NotificationLog.last_attempt_at < now - timedelta(days=90)
            )
        )
        await db.execute(delete(JobRun).where(JobRun.started_at < now - timedelta(days=30)))
        await db.commit()
    cleanup_expired_inbox()
