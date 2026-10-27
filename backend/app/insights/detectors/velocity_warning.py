import calendar

from app.insights.config import VELOCITY_PACE_BPS
from app.insights.helpers import make


def projected_month_end_spend(current_minor: int, now) -> int:
    """Use the same calendar-month extrapolation for insights and budgets."""
    days = calendar.monthrange(now.year, now.month)[1]
    return current_minor * days // now.day


def detect(view, settings, now):
    if now.day < 5:
        return []
    current = sum(
        t.amount
        for t in view.transactions
        if t.direction == "debit"
        and t.posted_at.year == now.year
        and t.posted_at.month == now.month
    )
    projected = projected_month_end_spend(current, now)
    income = (
        sum(
            t.amount
            for t in view.transactions
            if t.direction == "credit" and 0 <= (now - t.posted_at).days <= 90
        )
        // 3
    )
    historical = [
        t.amount
        for t in view.transactions
        if t.direction == "debit"
        and 30 < (now - t.posted_at).days <= 120
        and t.posted_at.day <= now.day
    ]
    typical = sum(historical) // 3
    if not income or not historical:
        return []
    if projected > income or current * 10000 > typical * VELOCITY_PACE_BPS:
        return [
            make(
                "behaviour",
                "velocity_warning",
                {
                    "projected_spend_minor": projected,
                    "expected_income_minor": income,
                    "overshoot_minor": max(0, projected - income),
                },
                severity="warning",
            )
        ]
    return []
