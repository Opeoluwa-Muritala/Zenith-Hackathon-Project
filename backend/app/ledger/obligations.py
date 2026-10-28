"""Persist high-confidence lender repayments found by the recurring detector."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ledger.normalise import lender_name
from app.ledger.service import as_utc
from app.models import (
    Direction,
    Merchant,
    Obligation,
    ObligationPayment,
    RecurringSeries,
    Transaction,
)


async def sync_detected_obligations(db: AsyncSession, user_id: UUID) -> int:
    recurring = (
        await db.execute(
            select(RecurringSeries, Merchant)
            .join(Merchant, RecurringSeries.merchant_id == Merchant.id)
            .where(RecurringSeries.user_id == user_id, RecurringSeries.direction == Direction.debit)
        )
    ).all()
    count = 0
    for series, merchant in recurring:
        lender = lender_name(merchant.canonical_name)
        if lender is None:
            continue
        obligation = (
            await db.execute(
                select(Obligation).where(
                    Obligation.user_id == user_id,
                    Obligation.account_id == series.account_id,
                    Obligation.lender_name == lender,
                    Obligation.source == "detected",
                )
            )
        ).scalar_one_or_none()
        if obligation is None:
            obligation = Obligation(
                user_id=user_id,
                account_id=series.account_id,
                lender_name=lender,
                kind="loan",
                amount_minor=series.typical_amount_minor,
                cadence_days=series.cadence_days,
                next_due_date=as_utc(series.next_expected_at).date(),
                confidence_bps=min(10_000, series.cycles * 2_000),
                status="upcoming",
                source="detected",
            )
            db.add(obligation)
            await db.flush()
            count += 1
        else:
            obligation.amount_minor = series.typical_amount_minor
            obligation.cadence_days = series.cadence_days
            obligation.next_due_date = as_utc(series.next_expected_at).date()
        transactions = (
            await db.execute(
                select(Transaction).where(
                    Transaction.account_id == series.account_id,
                    Transaction.direction == Direction.debit,
                )
            )
        ).scalars()
        for tx in transactions:
            if lender_name(tx.decoded_merchant or tx.narration_clean) != lender:
                continue
            existing = (
                await db.execute(
                    select(ObligationPayment.id).where(ObligationPayment.transaction_id == tx.id)
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    ObligationPayment(
                        obligation_id=obligation.id,
                        transaction_id=tx.id,
                        paid_at=tx.posted_at,
                        amount_minor=tx.amount_minor,
                    )
                )
    return count
