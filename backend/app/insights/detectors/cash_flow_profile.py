"""Light, code-only cash-flow rhythm and runway profile."""

from collections import defaultdict
from datetime import datetime, timedelta

from app.insights.helpers import make
from app.insights.types import Insight, LedgerView, Settings


def detect(view: LedgerView, settings: Settings, now: datetime) -> list[Insight]:
    transactions = [tx for tx in view.transactions if now - tx.posted_at <= timedelta(days=90)]
    if not transactions:
        return []
    weeks: dict[str, int] = defaultdict(int)
    inflow = outflow = 0
    for tx in transactions:
        week = f"{tx.posted_at.isocalendar().year}-W{tx.posted_at.isocalendar().week:02d}"
        signed = tx.amount if tx.direction == "credit" else -tx.amount
        weeks[week] += signed
        if tx.direction == "credit":
            inflow += tx.amount
        else:
            outflow += tx.amount
    ordered = sorted(weeks)
    average_weekly_outflow = outflow * 7 // 90
    cash = sum(max(0, balance.amount) for balance in view.balances)
    runway_days = cash * 7 // average_weekly_outflow if average_weekly_outflow else None
    return [
        make(
            "cashflow",
            "cash_flow_profile",
            {
                "period_days": 90,
                "inflow_minor": inflow,
                "outflow_minor": outflow,
                "best_week": max(weeks, key=lambda week: weeks[week]),
                "best_week_net_minor": max(weeks.values()),
                "worst_week": min(weeks, key=lambda week: weeks[week]),
                "worst_week_net_minor": min(weeks.values()),
                "runway_days": runway_days,
                "weekly_net_minor": [{"week": week, "net_minor": weeks[week]} for week in ordered],
                "transaction_ids": [tx.id for tx in transactions],
                "confidence_bps": 9000,
                "why_it_matters": "Cash-flow timing can expose weeks when available cash is tight.",
                "action": "Plan large payments around your stronger inflow weeks.",
            },
        )
    ]
