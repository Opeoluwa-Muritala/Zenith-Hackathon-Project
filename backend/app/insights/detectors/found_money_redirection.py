from app.insights.helpers import make, recent


def detect(view, settings, now):
    out = []
    for s in view.recurring:
        freed = (
            s.typical_amount
            if s.status in {"lapsed", "cancelled"}
            else max(0, (s.previous_amount or s.last_amount) - s.last_amount)
        )
        if freed:
            out.append(
                make(
                    "wealth",
                    "found_money_redirection",
                    {"source": s.merchant, "monthly_minor": freed, "annualised_minor": freed * 12},
                    s.id,
                )
            )
    normal = sum(t.amount for t in recent(view, now, 90, "credit")) // 3
    for t in recent(view, now, 30, "credit"):
        if normal and t.amount > normal * 2:
            out.append(
                make(
                    "wealth",
                    "found_money_redirection",
                    {
                        "source": "one_off_credit",
                        "monthly_minor": t.amount,
                        "annualised_minor": t.amount,
                    },
                    t.id,
                )
            )
    return out
