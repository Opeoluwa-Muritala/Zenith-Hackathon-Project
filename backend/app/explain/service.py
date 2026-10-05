"""Template explanations; replaceable without changing detectors."""

from abc import ABC, abstractmethod


class ExplanationService(ABC):
    @abstractmethod
    def explain(self, kind: str, payload: dict) -> tuple[str, str]: ...


class TemplateExplanationService(ExplanationService):
    """Render conservative copy that never claims knowledge absent from bank data."""

    TITLES = {
        "safe_to_spend": "Your safe-to-spend guide",
        "income_expense_crossover": "Spending may overtake income",
        "bill_spike": "A bill looks higher",
        "zombie_subscription": "Still using this?",
        "renewal_countdown": "Charges coming soon",
        "double_charge_price_change": "Check this charge",
        "temporal_spending_spikes": "A spending pattern stands out",
        "merchant_monopoly": "One merchant dominates",
        "velocity_warning": "Spending is moving quickly",
        "found_money_redirection": "Put freed money to work",
        "opportunity_cost_swap": "A possible spending swap",
        "idle_cash_optimisation": "Some cash may be idle",
    }

    def explain(self, kind, payload):
        title = self.TITLES.get(kind, "Financial insight")
        body = {
            "zombie_subscription": f"{payload.get('merchant', 'This service')} keeps charging. Bank data cannot show whether you use it.",
            "opportunity_cost_swap": "This treasury-bill-style return is an illustration, not a guarantee or advice.",
        }.get(kind, "Review the figures and decide what fits your plans.")
        return title, body


WEALTH_FOOTER = "Educational information, not financial advice."
