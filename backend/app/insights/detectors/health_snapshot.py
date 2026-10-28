"""Weekly consumer/SME financial health snapshot with three explainable drivers."""

from datetime import datetime, timedelta

from app.insights.helpers import make
from app.insights.types import Insight, LedgerView, Settings


def detect(view: LedgerView, settings: Settings, now: datetime) -> list[Insight]:
    tx = [item for item in view.transactions if now - item.posted_at <= timedelta(days=90)]
    if not tx:
        return []
    inflow = sum(item.amount for item in tx if item.direction == "credit")
    outflow = sum(item.amount for item in tx if item.direction == "debit")
    cash = sum(max(0, balance.amount) for balance in view.balances)
    savings_bps = (
        max(-10000, min(10000, (inflow - outflow) * 10000 // inflow)) if inflow else -10000
    )
    stability = max(0, 100 - min(100, abs(inflow - outflow) * 100 // max(1, inflow)))
    coverage = min(100, cash * 90 // max(1, outflow))
    savings_score = max(0, min(100, 50 + savings_bps // 200))
    score = (savings_score * 40 + stability * 30 + coverage * 30) // 100
    mode = settings.profile_mode if settings.profile_mode in {"consumer", "sme"} else "consumer"
    return [
        make(
            "cashflow",
            "health_snapshot",
            {
                "score": score,
                "mode": mode,
                "week": now.date().isoformat(),
                "drivers": [
                    {"name": "margin", "score": savings_score, "value_bps": savings_bps},
                    {"name": "cash_flow_stability", "score": stability},
                    {"name": "cash_coverage", "score": coverage},
                ],
                "transaction_ids": [item.id for item in tx],
                "confidence_bps": 9000,
                "why_it_matters": (
                    "The score combines margin, cash-flow stability and cash coverage."
                ),
                "action": "Review the lowest driver first.",
            },
            key=f"{mode}:{now.date().isocalendar().year}-W{now.date().isocalendar().week:02d}",
        )
    ]
