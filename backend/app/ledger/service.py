"""Consent-filtered ledger loading and idempotent transaction ingestion."""

import hashlib
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import now_utc
from app.insights.types import Balance, LedgerView, Series, Settings, Tx
from app.ledger.normalise import (
    categorise,
    category_label,
    clean_narration,
    counterparty_key,
    dedupe,
)
from app.models import (
    Account,
    CategoryRule,
    CategorySource,
    Channel,
    Consent,
    Direction,
    Merchant,
    RecurringSeries,
    ReviewedGlobalRule,
    Transaction,
    TransferSuggestion,
    UserSettings,
)
from app.providers.base import ProviderTransaction


def as_utc(value: datetime | None) -> datetime | None:
    """Restore UTC for database drivers that return naive timestamps."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def active_accounts(user_id: UUID, now: datetime):
    """Return an SQL subquery scoped to active consent and one owner."""
    return (
        select(Account.id)
        .join(Consent, Account.consent_id == Consent.id)
        .where(
            Account.user_id == user_id,
            Consent.user_id == user_id,
            Consent.revoked_at.is_(None),
            Consent.expires_at > now,
        )
    )


async def ledger_view(
    db: AsyncSession, user_id: UUID, now: datetime
) -> tuple[LedgerView, Settings]:
    """Build one authorised view for reporting, detectors and assistant tools."""
    account_ids = active_accounts(user_id, now)
    accounts = (
        (
            await db.execute(
                select(Account)
                .options(selectinload(Account.institution))
                .where(Account.id.in_(account_ids))
            )
        )
        .scalars()
        .all()
    )
    transactions = (
        (await db.execute(select(Transaction).where(Transaction.account_id.in_(account_ids))))
        .scalars()
        .all()
    )
    merchant_ids = {t.merchant_id for t in transactions if t.merchant_id}
    merchants = {
        m.id: m
        for m in (await db.execute(select(Merchant).where(Merchant.id.in_(merchant_ids)))).scalars()
    }
    series_rows = (
        (
            await db.execute(
                select(RecurringSeries).where(
                    RecurringSeries.user_id == user_id, RecurringSeries.account_id.in_(account_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    series_merchants = {
        m.id: m
        for m in (
            await db.execute(
                select(Merchant).where(Merchant.id.in_({s.merchant_id for s in series_rows}))
            )
        ).scalars()
    }
    settings_row = await db.get(UserSettings, user_id)
    settings = Settings(
        safe_buffer=settings_row.safe_buffer_minor if settings_row else 500_000,
        payday_hint=settings_row.payday_hint if settings_row else None,
        discretionary=tuple(
            category_label(category) for category in settings_row.discretionary_categories
        )
        if settings_row and settings_row.discretionary_categories
        else Settings().discretionary,
        nominal_tbill_rate_bps=settings_row.nominal_tbill_rate_bps if settings_row else 1500,
    )
    movement: dict[UUID, datetime] = {}
    for transaction in transactions:
        previous = movement.get(transaction.account_id)
        if previous is None or transaction.posted_at > previous:
            movement[transaction.account_id] = transaction.posted_at
    view = LedgerView(
        transactions=tuple(
            Tx(
                str(t.id),
                cast(datetime, as_utc(t.posted_at)),
                t.amount_minor,
                t.direction.value,
                category_label(t.category),
                merchants[t.merchant_id].canonical_name if t.merchant_id in merchants else "",
                merchants[t.merchant_id].is_subscription_like
                if t.merchant_id in merchants
                else False,
                merchants[t.merchant_id].legitimately_repeating
                if t.merchant_id in merchants
                else False,
            )
            for t in transactions
        ),
        balances=tuple(
            Balance(
                str(a.id),
                a.current_balance_minor,
                a.type.value,
                a.institution.savings_rate_bps,
                as_utc(movement.get(a.id)),
            )
            for a in accounts
        ),
        recurring=tuple(
            Series(
                str(s.id),
                series_merchants[s.merchant_id].canonical_name,
                category_label(series_merchants[s.merchant_id].category_default),
                s.cadence_days,
                s.typical_amount_minor,
                s.last_amount_minor,
                s.previous_amount_minor,
                s.cycles,
                cast(datetime, as_utc(s.next_expected_at)),
                s.status.value,
                series_merchants[s.merchant_id].is_subscription_like,
                s.direction.value,
            )
            for s in series_rows
            if s.merchant_id in series_merchants
        ),
    )
    return view, settings


async def ingest(db: AsyncSession, account: Account, rows: list[ProviderTransaction]) -> int:
    """Persist validated provider rows once per account; return inserted count."""
    count = 0
    await db.execute(select(Account.id).where(Account.id == account.id).with_for_update())
    occurrences: dict[tuple, int] = {}
    from app.ledger.classifier import default_classifier

    rules = {
        rule.counterparty_key: rule.category
        for rule in (
            await db.execute(select(CategoryRule).where(CategoryRule.user_id == account.user_id))
        ).scalars()
    }
    for row in rows:
        if type(row.amount_minor) is not int or row.amount_minor <= 0 or row.amount_minor >= 2**63:
            raise ValueError("Invalid transaction amount")
        if row.direction not in {"credit", "debit"} or row.posted_at.tzinfo is None:
            raise ValueError("Invalid transaction direction or timestamp")
        dedupe_key = dedupe(
            account.id, row.external_id, row.posted_at, row.amount_minor, row.direction
        )
        if (
            await db.execute(
                select(Transaction.id).where(
                    Transaction.account_id == account.id, Transaction.dedupe_hash == dedupe_key
                )
            )
        ).scalar_one_or_none():
            continue
        clean = clean_narration(row.narration)
        fingerprint = (
            row.source,
            row.posted_at.date(),
            row.amount_minor,
            row.direction,
            counterparty_key(row.narration),
        )
        occurrences[fingerprint] = occurrences.get(fingerprint, 0) + 1
        duplicates = (
            await db.scalars(
                select(Transaction).where(
                    Transaction.account_id == account.id,
                    Transaction.amount_minor == row.amount_minor,
                    Transaction.direction == Direction(row.direction),
                )
            )
        ).all()
        matches = sum(
            tx.source != row.source
            and tx.posted_at.date() == row.posted_at.date()
            and counterparty_key(tx.narration_raw) == counterparty_key(row.narration)
            for tx in duplicates
        )
        if matches >= occurrences[fingerprint]:
            continue
        name, category, subscription = categorise(row.narration, row.category)
        merchant_category = category
        key = counterparty_key(name)
        source = CategorySource.auto
        method = "provider" if row.category else "rule"
        global_rule = await db.scalar(
            select(ReviewedGlobalRule).where(
                ReviewedGlobalRule.narration_hash == hashlib.sha256(key.encode()).hexdigest()
            )
        )
        if global_rule:
            category, method = global_rule.category, "global_rule"
        if category == "Uncategorised" and key not in rules:
            prediction = await default_classifier.classify(row.narration)
            if prediction is not None:
                name, category = prediction.merchant, prediction.category
                method = "model"
                key = counterparty_key(name)
        if key in rules:
            category = category_label(rules[key])
            source = CategorySource.user_rule
            method = "user_rule"
        merchant = (
            await db.execute(select(Merchant).where(Merchant.canonical_name == name))
        ).scalar_one_or_none()
        if merchant is None:
            merchant = Merchant(
                canonical_name=name,
                category_default=merchant_category,
                is_subscription_like=subscription,
                legitimately_repeating=False,
            )
            db.add(merchant)
            await db.flush()
        channel = next((value for value in Channel if value.value in clean.upper()), Channel.OTHER)
        db.add(
            Transaction(
                account_id=account.id,
                posted_at=row.posted_at,
                amount_minor=row.amount_minor,
                direction=Direction(row.direction),
                narration_raw=row.narration,
                narration_clean=clean,
                decoded_merchant=name,
                merchant_id=merchant.id,
                category=category,
                category_source=source,
                channel=channel,
                balance_after_minor=row.balance_after_minor,
                dedupe_hash=dedupe_key,
                source=row.source,
                parse_confidence_bps=row.parse_confidence,
                classification_method=method,
            )
        )
        count += 1
        await db.flush()
    from app.ledger.normalise import detect_ajo_esusu

    history = (
        await db.scalars(
            select(Transaction).join(Account).where(Account.user_id == account.user_id)
        )
    ).all()
    groups: dict[str, list[Transaction]] = {}
    for tx in history:
        if tx.channel in {Channel.NIP, Channel.USSD}:
            groups.setdefault(
                counterparty_key(tx.decoded_merchant or tx.narration_clean), []
            ).append(tx)
    for key, items in groups.items():
        debits = [
            (tx.posted_at, tx.amount_minor, key) for tx in items if tx.direction == Direction.debit
        ]
        credits = [
            (tx.posted_at, tx.amount_minor, key) for tx in items if tx.direction == Direction.credit
        ]
        kinds = []
        if len(debits) >= 2 and len({item[0].date() for item in debits}) >= 2:
            kinds.append("family")
        if detect_ajo_esusu(debits, credits):
            kinds.append("ajo")
        for kind in kinds:
            existing = await db.scalar(
                select(TransferSuggestion).where(
                    TransferSuggestion.user_id == account.user_id,
                    TransferSuggestion.counterparty_key == key,
                    TransferSuggestion.kind == kind,
                )
            )
            if existing is None:
                db.add(
                    TransferSuggestion(
                        user_id=account.user_id,
                        counterparty_key=key,
                        kind=kind,
                        status="pending",
                        created_at=now_utc(),
                    )
                )
    account.last_synced_at = now_utc()
    return count
