from datetime import timedelta

from app.insights.config import DUPLICATE_HOURS, PRICE_CHANGE_BPS
from app.insights.helpers import make


def detect(view, settings, now):
    out = []
    tx = sorted([t for t in view.transactions if t.direction == "debit"], key=lambda t: t.posted_at)
    for i, a in enumerate(tx):
        for b in tx[i + 1 :]:
            if b.posted_at - a.posted_at > timedelta(hours=DUPLICATE_HOURS):
                break
            if (
                a.merchant
                and a.merchant == b.merchant
                and a.amount == b.amount
                and not a.legitimately_repeating
            ):
                out.append(
                    make(
                        "leaks",
                        "double_charge_price_change",
                        {
                            "type": "duplicate",
                            "merchant": a.merchant,
                            "transaction_ids": [a.id, b.id],
                            "delta_minor": 0,
                        },
                        f"{a.id}:{b.id}",
                        "warning",
                    )
                )
    for s in view.recurring:
        if (
            s.previous_amount
            and abs(s.last_amount - s.previous_amount) * 10000
            >= s.previous_amount * PRICE_CHANGE_BPS
        ):
            out.append(
                make(
                    "leaks",
                    "double_charge_price_change",
                    {
                        "type": "price_change",
                        "merchant": s.merchant,
                        "previous_minor": s.previous_amount,
                        "current_minor": s.last_amount,
                        "delta_minor": s.last_amount - s.previous_amount,
                    },
                    s.id,
                    "warning",
                )
            )
    return out
