"""Ordered registry of every detector."""

from app.insights.detectors import (
    bill_spike,
    double_charge_price_change,
    found_money_redirection,
    idle_cash_optimisation,
    income_expense_crossover,
    merchant_monopoly,
    opportunity_cost_swap,
    renewal_countdown,
    safe_to_spend,
    temporal_spending_spikes,
    velocity_warning,
    zombie_subscription,
)

DETECTORS = (
    safe_to_spend,
    income_expense_crossover,
    bill_spike,
    zombie_subscription,
    renewal_countdown,
    double_charge_price_change,
    temporal_spending_spikes,
    merchant_monopoly,
    velocity_warning,
    found_money_redirection,
    opportunity_cost_swap,
    idle_cash_optimisation,
)


def run_all(view, settings, now):
    return [item for detector in DETECTORS for item in detector.detect(view, settings, now)]
