from collections import defaultdict
from datetime import timedelta

from app.insights.types import Insight


def make(module, kind, payload, key="current", severity="info"):
    return Insight(module, kind, severity, payload, f"{kind}:{key}")


def recent(view, now, days, direction=None):
    return [
        t
        for t in view.transactions
        if now - t.posted_at <= timedelta(days=days)
        and (direction is None or t.direction == direction)
    ]


def grouped(items, key):
    out = defaultdict(int)
    for item in items:
        out[key(item)] += item.amount
    return out
