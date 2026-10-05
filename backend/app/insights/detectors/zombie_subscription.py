from app.insights.helpers import make


def detect(view, settings, now):
    active = [
        s for s in view.recurring if s.status == "active" and s.subscription_like and s.cycles >= 3
    ]
    cats = {s.category for s in active if sum(x.category == s.category for x in active) > 1}
    return [
        make(
            "leaks",
            "zombie_subscription",
            {
                "merchant": s.merchant,
                "annualised_minor": s.last_amount * 365 // s.cadence_days,
                "prompt": "Still using this?",
                "actions": ["keep", "cancel_reminder"],
                "overlap": s.category in cats,
            },
            s.id,
            "warning",
        )
        for s in sorted(active, key=lambda s: s.last_amount * 365 // s.cadence_days, reverse=True)
    ]
