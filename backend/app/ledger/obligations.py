"""Persist high-confidence lender repayments found by the recurring detector."""

import re
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ledger.normalise import lender_name, narration_parts
from app.ledger.service import as_utc
from app.models import (
    Direction,
    Merchant,
    Obligation,
    ObligationPayment,
    RecurringSeries,
    Transaction,
)


def obligation_lender(value: str) -> tuple[str, str] | None:
    """Match the reviewed lender list, then conservative generic repayment terms."""
    known = lender_name(value)
    if known:
        return known, "loan"
    lower = value.lower()
    if not re.search(r"\b(?:loan|repayment|direct[ -]?debit)\b", lower):
        return None
    kind = "direct_debit" if re.search(r"\bdirect[ -]?debit\b", lower) else "loan"
    decoded = " ".join(narration_parts(value)).strip()
    return (decoded[:120] or ("Direct debit" if kind == "direct_debit" else "Loan repayment"), kind)


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
        match = obligation_lender(merchant.canonical_name)
        if match is None:
            continue
        lender, kind = match
        next_due = cast(datetime, as_utc(series.next_expected_at)).date()
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
                kind=kind,
                amount_minor=series.typical_amount_minor,
                cadence_days=series.cadence_days,
                next_due_date=next_due,
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
            obligation.next_due_date = next_due
            obligation.kind = kind
            obligation.confidence_bps = min(10_000, series.cycles * 2_000)
        transactions = (
            await db.execute(
                select(Transaction).where(
                    Transaction.account_id == series.account_id,
                    Transaction.direction == Direction.debit,
                )
            )
        ).scalars()
        for tx in transactions:
            transaction_match = obligation_lender(tx.decoded_merchant or tx.narration_clean)
            if transaction_match is None or transaction_match[0] != lender:
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
