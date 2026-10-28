"""Build one deterministic monthly report from the consent-filtered ledger."""

import calendar
from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights.business import suggest_use
from app.ledger.normalise import category_label
from app.ledger.service import active_accounts
from app.models import Merchant, Transaction, TransactionUseLabel


class ReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    posted_at: datetime
    amount_minor: int
    direction: str
    merchant: str
    category: str
    use_label: str
    confidence_bps: int


class UncertainItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    amount_minor: int
    reason: str


class MonthlyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str
    currency: str = "NGN"
    income_minor: int
    expenses_minor: int
    net_cash_flow_minor: int
    business_expenses_minor: int
    personal_expenses_minor: int
    unsure_expenses_minor: int
    weekly_net_minor: list[dict[str, int | str]]
    transactions: list[ReportItem]
    uncertain_items: list[UncertainItem]
    generated_at: datetime


def parse_month(value: str) -> date:
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM") from exc
    return parsed.replace(day=1)


async def build_monthly_report(
    db: AsyncSession, user_id: UUID, month: date, generated_at: datetime
) -> MonthlyReport:
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    end = datetime(
        month.year + (1 if month.month == 12 else 0),
        1 if month.month == 12 else month.month + 1,
        1,
        tzinfo=UTC,
    )
    rows = (
        await db.execute(
            select(Transaction, Merchant)
            .outerjoin(Merchant, Transaction.merchant_id == Merchant.id)
            .where(
                Transaction.account_id.in_(active_accounts(user_id, generated_at)),
                Transaction.posted_at >= start,
                Transaction.posted_at < end,
            )
            .order_by(Transaction.posted_at.asc(), Transaction.id.asc())
        )
    ).all()
    transaction_ids = [transaction.id for transaction, _ in rows]
    labels = {
        item.transaction_id: item
        for item in (
            await db.scalars(
                select(TransactionUseLabel).where(
                    TransactionUseLabel.user_id == user_id,
                    TransactionUseLabel.transaction_id.in_(transaction_ids),
                )
            )
        ).all()
    }
    items: list[ReportItem] = []
    uncertain: list[UncertainItem] = []
    income = expenses = 0
    split = {"business": 0, "personal": 0, "unsure": 0}
    weeks: dict[str, int] = defaultdict(int)
    for transaction, merchant in rows:
        suggestion, suggested_confidence = suggest_use(transaction)
        reviewed = labels.get(transaction.id)
        use_label = (
            reviewed.confirmed_label if reviewed and reviewed.confirmed_label else suggestion
        )
        confidence = min(
            transaction.parse_confidence_bps,
            10_000 if reviewed and reviewed.confirmed_label else suggested_confidence,
        )
        amount = transaction.amount_minor
        signed = amount if transaction.direction.value == "credit" else -amount
        week = min(5, (transaction.posted_at.day - 1) // 7 + 1)
        weeks[f"week_{week}"] += signed
        if transaction.direction.value == "credit":
            income += amount
        else:
            expenses += amount
            split[use_label] += amount
        item = ReportItem(
            transaction_id=transaction.id,
            posted_at=transaction.posted_at,
            amount_minor=amount,
            direction=transaction.direction.value,
            merchant=(
                merchant.canonical_name if merchant else transaction.decoded_merchant or "Unknown"
            ),
            category=category_label(transaction.category),
            use_label=use_label,
            confidence_bps=confidence,
        )
        items.append(item)
        reasons = []
        if use_label == "unsure":
            reasons.append("business/personal use is unsure")
        if confidence < 7000:
            reasons.append("classification confidence is low")
        if reasons:
            uncertain.append(
                UncertainItem(
                    transaction_id=transaction.id,
                    amount_minor=amount,
                    reason="; ".join(reasons),
                )
            )
    return MonthlyReport(
        month=month.strftime("%Y-%m"),
        income_minor=income,
        expenses_minor=expenses,
        net_cash_flow_minor=income - expenses,
        business_expenses_minor=split["business"],
        personal_expenses_minor=split["personal"],
        unsure_expenses_minor=split["unsure"],
        weekly_net_minor=[
            {"week": f"week_{week}", "net_minor": weeks.get(f"week_{week}", 0)}
            for week in range(
                1,
                min(5, (calendar.monthrange(month.year, month.month)[1] - 1) // 7 + 1) + 1,
            )
        ],
        transactions=items,
        uncertain_items=uncertain,
        generated_at=generated_at,
    )
