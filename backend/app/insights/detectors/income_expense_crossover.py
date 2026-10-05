from datetime import timedelta

from app.insights.helpers import make


def detect(view, settings, now):
    if not view.transactions or min(t.posted_at for t in view.transactions) > now - timedelta(
        days=90
    ):
        return []
    margins = []
    for i in (2, 1, 0):
        end = now - timedelta(days=30 * i)
        start = end - timedelta(days=30)
        margins.append(
            sum(
                t.amount if t.direction == "credit" else -t.amount
                for t in view.transactions
                if start < t.posted_at <= end
            )
        )
    slope = (margins[2] - margins[0]) // 2
    if margins[2] < 0:
        date = now.date()
    elif slope < 0 and margins[2] + slope < 0:
        date = (now + timedelta(days=max(1, min(30, margins[2] * 30 // -slope)))).date()
    else:
        return []
    return [
        make(
            "cashflow",
            "income_expense_crossover",
            {"projected_crossover_date": date.isoformat(), "margin_minor": margins[2]},
            severity="warning",
        )
    ]
