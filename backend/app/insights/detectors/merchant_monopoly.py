from app.insights.config import MERCHANT_MONOPOLY_BPS
from app.insights.helpers import grouped, make, recent


def detect(view, settings, now):
    tx = [
        t
        for t in recent(view, now, 30, "debit")
        if t.category in settings.discretionary and t.merchant
    ]
    if len(tx) < 3:
        return []
    total = sum(t.amount for t in tx)
    groups = grouped(tx, lambda t: t.merchant)
    merchant, amount = max(groups.items(), key=lambda x: x[1])
    return (
        [
            make(
                "behaviour",
                "merchant_monopoly",
                {
                    "merchant": merchant,
                    "amount_minor": amount,
                    "share_bps": amount * 10000 // total,
                },
                merchant,
                "warning",
            )
        ]
        if amount * 10000 > total * MERCHANT_MONOPOLY_BPS
        else []
    )
