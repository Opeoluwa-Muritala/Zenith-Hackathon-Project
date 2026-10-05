from app.insights.config import BILL_SPIKE_RATIO_BPS
from app.insights.helpers import make


def detect(view, settings, now):
    out = []
    for s in view.recurring:
        if (
            s.cycles >= 4
            and s.typical_amount
            and s.last_amount * 10000 > s.typical_amount * BILL_SPIKE_RATIO_BPS
        ):
            out.append(
                make(
                    "cashflow",
                    "bill_spike",
                    {
                        "merchant": s.merchant,
                        "amount_minor": s.last_amount,
                        "jump_bps": (s.last_amount - s.typical_amount) * 10000 // s.typical_amount,
                    },
                    s.id,
                    "warning",
                )
            )
    months = {}
    for t in view.transactions:
        if t.direction == "debit" and t.category == "utilities":
            months[(t.posted_at.year, t.posted_at.month)] = (
                months.get((t.posted_at.year, t.posted_at.month), 0) + t.amount
            )
    cur = months.get((now.year, now.month), 0)
    prior = [v for k, v in sorted(months.items()) if k != (now.year, now.month)][-3:]
    if len(prior) == 3 and (avg := sum(prior) // 3) and cur * 10000 > avg * BILL_SPIKE_RATIO_BPS:
        out.append(
            make(
                "cashflow",
                "bill_spike",
                {
                    "category": "utilities",
                    "amount_minor": cur,
                    "jump_bps": (cur - avg) * 10000 // avg,
                },
                "utilities",
                "warning",
            )
        )
    return out
