"""Conservative unusual-transfer detector based on the user's own history."""

from datetime import datetime, timedelta
from statistics import median

from app.insights.helpers import make
from app.insights.types import Insight, LedgerView, Settings


def detect(view: LedgerView, settings: Settings, now: datetime) -> list[Insight]:
    transfers = [
        tx
        for tx in view.transactions
        if tx.direction == "debit" and tx.category == "Transfers & Family"
    ]
    history = [tx.amount for tx in transfers if (now - tx.posted_at).days > 7]
    current = [tx for tx in transfers if now - tx.posted_at <= timedelta(days=7)]
    if len(history) < 3:
        return []
    typical = int(median(history))
    unusual = [tx for tx in current if tx.amount >= max(100_000, typical * 3)]
    if not unusual:
        return []
    amount = sum(tx.amount for tx in unusual)
    return [
        make(
            "cashflow",
            "unusual_transfer",
            {
                "amount_minor": amount,
                "typical_minor": typical,
                "transaction_ids": [tx.id for tx in unusual],
                "confidence_bps": 8000,
                "why_it_matters": "The transfer is much larger than your recent transfer history.",
                "action": "Confirm that you recognise the recipient and amount.",
            },
            severity="warning",
        )
    ]
