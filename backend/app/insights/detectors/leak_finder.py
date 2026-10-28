"""Deterministic headline aggregation for avoidable-looking charges."""

from datetime import datetime, timedelta

from app.insights.helpers import make
from app.insights.types import Insight, LedgerView, Settings


def detect(view: LedgerView, settings: Settings, now: datetime) -> list[Insight]:
    candidates: dict[str, int] = {}
    evidence: list[str] = []
    recent = [
        tx
        for tx in view.transactions
        if tx.direction == "debit" and now - tx.posted_at <= timedelta(days=90)
    ]
    for index, first in enumerate(sorted(recent, key=lambda tx: tx.posted_at)):
        merchant_key = first.merchant.lower()
        if any(
            token in merchant_key for token in ("fee", "charge", "vat", "stamp duty", "maintenance")
        ):
            candidates[f"fee:{first.id}"] = first.amount
            evidence.append(first.id)
        for second in recent[index + 1 :]:
            if second.posted_at - first.posted_at > timedelta(hours=48):
                break
            if (
                first.merchant
                and first.merchant == second.merchant
                and first.amount == second.amount
                and not first.legitimately_repeating
            ):
                candidates[f"duplicate:{first.id}:{second.id}"] = second.amount
                evidence.extend((first.id, second.id))
    for series in view.recurring:
        if series.status == "active" and series.subscription_like and series.cycles >= 3:
            candidates[f"subscription:{series.id}"] = series.last_amount
            evidence.extend(tx.id for tx in recent if tx.merchant == series.merchant)
        if series.previous_amount and series.last_amount > series.previous_amount:
            candidates[f"increase:{series.id}"] = series.last_amount - series.previous_amount
            evidence.extend(tx.id for tx in recent if tx.merchant == series.merchant)
    amount = sum(candidates.values())
    if not amount:
        return []
    return [
        make(
            "leaks",
            "leak_finder_headline",
            {
                "amount_minor": amount,
                "candidate_count": len(candidates),
                "transaction_ids": list(dict.fromkeys(evidence)),
                "confidence_bps": 8500,
                "why_it_matters": "These charges may be avoidable and are worth reviewing.",
                "action": "Review the evidence and confirm which charges are expected.",
            },
            severity="warning",
        )
    ]
