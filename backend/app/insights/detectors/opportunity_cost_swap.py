from app.insights.config import OPPORTUNITY_SLICE_BPS
from app.insights.helpers import grouped, make, recent


def detect(view, settings, now):
    tx = [t for t in recent(view, now, 30, "debit") if t.category in settings.discretionary]
    if len(tx) < 3:
        return []
    category, amount = max(grouped(tx, lambda t: t.category).items(), key=lambda x: x[1])
    moved = amount * OPPORTUNITY_SLICE_BPS // 10000
    value = moved + moved * settings.nominal_tbill_rate_bps // 10000
    return [
        make(
            "wealth",
            "opportunity_cost_swap",
            {
                "category": category,
                "monthly_spend_minor": amount,
                "redirect_minor": moved,
                "illustrated_12m_value_minor": value,
                "rate_bps": settings.nominal_tbill_rate_bps,
                "disclaimer": "Illustration, not a guarantee or advice.",
            },
            category,
        )
    ]
