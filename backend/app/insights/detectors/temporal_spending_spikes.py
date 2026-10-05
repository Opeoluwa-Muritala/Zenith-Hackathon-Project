from collections import defaultdict

from app.insights.config import TEMPORAL_MIN_SAMPLES, TEMPORAL_SPIKE_RATIO_BPS
from app.insights.helpers import make, recent


def detect(view, settings, now):
    tx = [t for t in recent(view, now, 90, "debit") if t.category in settings.discretionary]
    if len(tx) < TEMPORAL_MIN_SAMPLES * 3:
        return []
    groups = defaultdict(list)
    for t in tx:
        groups[t.posted_at.weekday()].append(t.amount)
    avg = sum(t.amount for t in tx) // 7
    out = []
    for day, vals in groups.items():
        if len(vals) >= TEMPORAL_MIN_SAMPLES and sum(vals) * 10000 > avg * TEMPORAL_SPIKE_RATIO_BPS:
            amount = sum(vals)
            out.append(
                make(
                    "behaviour",
                    "temporal_spending_spikes",
                    {
                        "bucket": "weekday",
                        "weekday": day,
                        "amount_minor": amount,
                        "share_bps": amount * 10000 // sum(t.amount for t in tx),
                    },
                    str(day),
                    "info",
                )
            )
    return out
