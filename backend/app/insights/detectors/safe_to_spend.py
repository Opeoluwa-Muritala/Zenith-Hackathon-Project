from datetime import timedelta

from app.insights.helpers import make


def detect(view, settings, now):
    income = [t for t in view.transactions if t.direction == "credit" and t.posted_at <= now]
    if not income and settings.payday_hint is None:
        return []
    nxt = (
        max(income, key=lambda t: t.posted_at).posted_at + timedelta(days=30)
        if income
        else now + timedelta(days=max(1, (settings.payday_hint - now.day) % 28))
    )
    days = max(1, (nxt.date() - now.date()).days)
    bal = sum(b.amount for b in view.balances if b.account_type in {"current", "wallet"})
    due = sum(
        s.last_amount
        for s in view.recurring
        if s.direction == "debit" and now < s.next_expected_at <= nxt and s.status == "active"
    )
    daily = (bal - due - settings.safe_buffer) // days
    status = "negative" if daily < 0 else "tight" if daily < 100_000 else "comfortable"
    return [
        make(
            "cashflow",
            "safe_to_spend",
            {
                "daily_allowance_minor": daily,
                "status": status,
                "days": days,
                "committed_minor": due,
            },
        )
    ]
