"""Ordered registry of every detector."""

from app.insights.detectors import (
    bill_spike,
    cash_flow_profile,
    double_charge_price_change,
    found_money_redirection,
    health_snapshot,
    idle_cash_optimisation,
    income_expense_crossover,
    leak_finder,
    loan_repayment_due,
    merchant_monopoly,
    opportunity_cost_swap,
    renewal_countdown,
    safe_to_spend,
    temporal_spending_spikes,
    unusual_transfer,
    velocity_warning,
    zombie_subscription,
)

DETECTORS = (
    leak_finder,
    cash_flow_profile,
    health_snapshot,
    unusual_transfer,
    loan_repayment_due,
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
