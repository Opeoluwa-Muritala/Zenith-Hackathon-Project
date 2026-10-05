"""Pure integer-kobo calculations over an already authorised ledger view."""

from collections import defaultdict

from app.insights.detectors.safe_to_spend import detect as safe_to_spend
from app.insights.helpers import recent

TOOL_NAMES = (
    "get_financial_overview",
    "get_safe_to_spend",
    "get_spending_breakdown",
    "get_recurring_commitments",
    "get_cashflow_trend",
    "compare_spending_scenario",
    "calculate_savings_projection",
)


def calculate(name: str, view, settings, now, args: dict) -> dict:
    """Execute an allowlisted calculation; never accept an external user ID."""
    if name not in TOOL_NAMES or set(args) - {
        "category",
        "slice_bps",
        "principal_minor",
        "rate_bps",
    }:
        raise ValueError("Unknown tool or argument")
    if name == "get_financial_overview":
        tx = recent(view, now, 30)
        income = sum(t.amount for t in tx if t.direction == "credit")
        spend = sum(t.amount for t in tx if t.direction == "debit")
        return {
            "income_minor": income,
            "spend_minor": spend,
            "balance_minor": sum(b.amount for b in view.balances),
            "savings_rate_bps": (income - spend) * 10_000 // income if income else None,
            "period_days": 30,
        }
    if name == "get_safe_to_spend":
        result = safe_to_spend(view, settings, now)
        return result[0].payload if result else {"status": "insufficient_data"}
    if name == "get_spending_breakdown":
        tx = recent(view, now, 30, "debit")
        groups: dict[str, int] = defaultdict(int)
        for item in tx:
            groups[item.category] += item.amount
        total = sum(groups.values())
        return {
            "period_days": 30,
            "total_minor": total,
            "categories": [
                {
                    "category": key,
                    "amount_minor": value,
                    "share_bps": value * 10_000 // total if total else 0,
                }
                for key, value in sorted(groups.items())
            ],
        }
    if name == "get_recurring_commitments":
        series = [s for s in view.recurring if s.status == "active" and s.direction == "debit"]
        return {
            "items": [
                {
                    "merchant": s.merchant,
                    "amount_minor": s.last_amount,
                    "next_expected_at": s.next_expected_at.isoformat(),
                    "annualised_minor": s.last_amount * 365 // s.cadence_days,
                }
                for s in series
            ]
        }
    if name == "get_cashflow_trend":
        months: dict[str, dict[str, int]] = defaultdict(
            lambda: {"income_minor": 0, "spend_minor": 0}
        )
        for t in recent(view, now, 180):
            months[t.posted_at.strftime("%Y-%m")][
                "income_minor" if t.direction == "credit" else "spend_minor"
            ] += t.amount
        return {
            "months": [
                {"month": key, **value, "net_minor": value["income_minor"] - value["spend_minor"]}
                for key, value in sorted(months.items())
            ]
        }
    if name == "compare_spending_scenario":
        category = args.get("category")
        slice_bps = args.get("slice_bps")
        if (
            category not in settings.discretionary
            or type(slice_bps) is not int
            or not 1 <= slice_bps <= 5_000
        ):
            raise ValueError("Invalid scenario parameters")
        amount = sum(t.amount for t in recent(view, now, 30, "debit") if t.category == category)
        return {
            "category": category,
            "current_monthly_minor": amount,
            "reduction_bps": slice_bps,
            "monthly_freed_minor": amount * slice_bps // 10_000,
            "annual_freed_minor": amount * slice_bps * 12 // 10_000,
            "illustration": True,
        }
    principal = args.get("principal_minor")
    rate = args.get("rate_bps", settings.nominal_tbill_rate_bps)
    if type(principal) is not int or not 0 < principal <= 100_000_000_000:
        raise ValueError("Invalid principal")
    if type(rate) is not int or not 0 <= rate <= 10_000:
        raise ValueError("Invalid rate")
    return {
        "principal_minor": principal,
        "rate_bps": rate,
        "illustrated_interest_minor": principal * rate // 10_000,
        "illustrated_12m_value_minor": principal * (10_000 + rate) // 10_000,
        "illustration": True,
        "disclaimer": "Educational information, not financial advice.",
    }


def tool_schema(name: str) -> dict:
    """Return a strict Responses API function schema for one read-only tool."""
    properties = {
        "compare_spending_scenario": {
            "category": {"type": "string"},
            "slice_bps": {"type": "integer"},
        },
        "calculate_savings_projection": {
            "principal_minor": {"type": "integer"},
            "rate_bps": {"type": "integer"},
        },
    }.get(name, {})
    return {
        "type": "function",
        "name": name,
        "description": f"Read-only financial tool: {name}",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }
