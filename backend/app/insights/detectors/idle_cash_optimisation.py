from datetime import timedelta

from app.insights.config import HIGH_YIELD_BENCHMARK_BPS, IDLE_DAYS, LOW_RATE_BPS
from app.insights.helpers import make, recent


def detect(view, settings, now):
    expenses = sum(t.amount for t in recent(view, now, 90, "debit")) // 3
    out = []
    for b in view.balances:
        surplus = b.amount - settings.safe_buffer - expenses
        if (
            surplus > 0
            and b.savings_rate_bps < LOW_RATE_BPS
            and (
                b.last_movement_at is None or now - b.last_movement_at >= timedelta(days=IDLE_DAYS)
            )
        ):
            foregone = surplus * max(0, HIGH_YIELD_BENCHMARK_BPS - b.savings_rate_bps) // 10000
            out.append(
                make(
                    "wealth",
                    "idle_cash_optimisation",
                    {
                        "surplus_minor": surplus,
                        "foregone_annual_interest_minor": foregone,
                        "benchmark_bps": HIGH_YIELD_BENCHMARK_BPS,
                        "product": "configured_higher_yield_option",
                    },
                    b.account_id,
                )
            )
    return out
