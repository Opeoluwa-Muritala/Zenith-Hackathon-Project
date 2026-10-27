"""Strict aggregate-only tools over a consent-filtered LedgerView."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.redaction import tool_input
from app.insights.detectors.safe_to_spend import detect as safe_to_spend
from app.insights.helpers import recent
from app.insights.registry import run_all


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OverviewArgs(StrictArgs):
    period: Literal["7d", "30d", "90d"]


class DateRangeArgs(StrictArgs):
    start: date
    end: date


class MerchantArgs(DateRangeArgs):
    limit: int = Field(default=5, ge=1, le=10, strict=True)


class WeekArgs(StrictArgs):
    weeks: int = Field(default=8, ge=1, le=12, strict=True)


class EmptyArgs(StrictArgs):
    pass


class InsightArgs(StrictArgs):
    module: Literal["cashflow", "leaks", "behaviour", "wealth"] | None = None


class AffordabilityArgs(StrictArgs):
    amount_minor: int = Field(gt=0, le=100_000_000_000, strict=True)
    by_date: date | None = None


ARG_MODELS: dict[str, type[BaseModel]] = {
    "get_overview": OverviewArgs,
    "get_spend_by_category": DateRangeArgs,
    "get_top_merchants": MerchantArgs,
    "get_cashflow_by_week": WeekArgs,
    "get_recurring": EmptyArgs,
    "get_safe_to_spend": EmptyArgs,
    "get_active_insights": InsightArgs,
    "affordability_check": AffordabilityArgs,
}

TOOLS = [
    {
        "name": "get_overview",
        "description": "Get income, spending, savings rate and balance for a recent period.",
        "input_schema": {
            "type": "object",
            "properties": {"period": {"type": "string", "enum": ["7d", "30d", "90d"]}},
            "required": ["period"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_spend_by_category",
        "description": "Get aggregate spending by category for an allowed date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "format": "date"},
                "end": {"type": "string", "format": "date"},
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_top_merchants",
        "description": "Get canonical merchant aggregates, never individual transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "format": "date"},
                "end": {"type": "string", "format": "date"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_cashflow_by_week",
        "description": "Get weekly income, spending and net totals.",
        "input_schema": {
            "type": "object",
            "properties": {"weeks": {"type": "integer", "minimum": 1, "maximum": 12}},
            "required": ["weeks"],
            "additionalProperties": False,
        },
    },
    *[
        {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
        for name, description in (
            ("get_recurring", "Get recurring bills with amounts, cadence and next dates."),
            ("get_safe_to_spend", "Run the deterministic safe-to-spend detector."),
        )
    ],
    {
        "name": "get_active_insights",
        "description": "Get current rule-based insights and their verified facts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": ["string", "null"],
                    "enum": ["cashflow", "leaks", "behaviour", "wealth", None],
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "affordability_check",
        "description": (
            "Calculate affordability from balance, due commitments and buffer. "
            "Amount is integer kobo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount_minor": {"type": "integer", "minimum": 1},
                "by_date": {"type": ["string", "null"], "format": "date"},
            },
            "required": ["amount_minor"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = tuple(TOOLS_TOOL["name"] for TOOLS_TOOL in TOOLS)
MAX_AFFORDABILITY_HORIZON_DAYS = 365


def _transactions_for_range(view, start: date, end: date, now: datetime):
    """Validate requested dates against available ledger bounds and return aggregates input."""
    if end < start or (end - start).days > 365 or end > now.date():
        raise ValueError("Requested date range is outside supported limits")
    oldest = min((tx.posted_at.date() for tx in view.transactions), default=None)
    if oldest is None or start < oldest:
        raise ValueError("Requested date range is outside available data")
    return [t for t in view.transactions if start <= t.posted_at.date() <= end]


def calculate(name: str, args: dict, view, settings, now: datetime) -> dict:
    """Validate strict model arguments and return small aggregate-only data."""
    if name not in ARG_MODELS:
        raise ValueError("Unknown tool")
    try:
        parsed = ARG_MODELS[name].model_validate(args)
    except ValidationError as exc:
        raise ValueError("Invalid tool arguments") from exc
    values = parsed.model_dump()
    if name == "get_overview":
        days = int(values["period"][:-1])
        tx = recent(view, now, days)
        income = sum(t.amount for t in tx if t.direction == "credit")
        spend = sum(t.amount for t in tx if t.direction == "debit")
        result = {
            "period_days": days,
            "income_minor": income,
            "spend_minor": spend,
            "balance_minor": sum(b.amount for b in view.balances),
            "savings_rate_bps": (income - spend) * 10_000 // income if income else None,
        }
    elif name in {"get_spend_by_category", "get_top_merchants"}:
        tx = _transactions_for_range(view, values["start"], values["end"], now)
        tx = [t for t in tx if t.direction == "debit"]
        field = "category" if name == "get_spend_by_category" else "merchant"
        sums: dict[str, int] = defaultdict(int)
        for item in tx:
            sums[getattr(item, field) or "Uncategorised"] += item.amount
        total = sum(sums.values())
        entries = [
            {
                field: key,
                "amount_minor": amount,
                "share_bps": amount * 10_000 // total if total else 0,
            }
            for key, amount in sorted(sums.items(), key=lambda row: (-row[1], row[0]))
        ]
        if name == "get_top_merchants":
            entries = entries[: values["limit"]]
        result = {
            "start_date": values["start"].isoformat(),
            "end_date": values["end"].isoformat(),
            "total_minor": total,
            "categories" if name == "get_spend_by_category" else "merchants": entries,
        }
    elif name == "get_cashflow_by_week":
        weeks = values["weeks"]
        start = now - timedelta(days=7 * weeks)
        buckets: dict[str, dict[str, int]] = defaultdict(
            lambda: {"income_minor": 0, "spend_minor": 0}
        )
        for tx in view.transactions:
            if start <= tx.posted_at <= now:
                monday = tx.posted_at.date() - timedelta(days=tx.posted_at.weekday())
                key = monday.isoformat()
                bucket = buckets[key]
                bucket["income_minor" if tx.direction == "credit" else "spend_minor"] += tx.amount
        result = {
            "weeks": [
                {"start_date": key, **data, "net_minor": data["income_minor"] - data["spend_minor"]}
                for key, data in sorted(buckets.items())
            ]
        }
    elif name == "get_recurring":
        result = {
            "items": [
                {
                    "merchant": s.merchant,
                    "category": s.category,
                    "amount_minor": s.last_amount,
                    "cadence_days": s.cadence_days,
                    "next_expected_at": s.next_expected_at.isoformat(),
                    "status": s.status,
                }
                for s in view.recurring
                if s.direction == "debit" and s.status == "active"
            ][:25]
        }
    elif name == "get_safe_to_spend":
        found = safe_to_spend(view, settings, now) if view.balances else []
        result = found[0].payload if found else {"status": "insufficient_data"}
    elif name == "get_active_insights":
        found = run_all(view, settings, now) if view.balances else []
        result = {
            "items": [
                {
                    "kind": item.kind,
                    "module": item.module,
                    "severity": item.severity,
                    "facts": item.payload,
                }
                for item in found
                if not values.get("module") or item.module == values["module"]
            ][:25]
        }
    else:
        requested = values["amount_minor"]
        by_date = values.get("by_date")
        if by_date and (
            by_date < now.date() or (by_date - now.date()).days > MAX_AFFORDABILITY_HORIZON_DAYS
        ):
            raise ValueError("Requested affordability date is outside supported limits")
        forecast = safe_to_spend(view, settings, now)
        if not forecast:
            result = {
                "amount_minor": requested,
                "verdict": "not_advised",
                "assumptions": ["Income timing is unavailable."],
            }
        else:
            due = int(forecast[0].payload["committed_minor"])
            spendable = sum(
                b.amount for b in view.balances if b.account_type in {"current", "wallet"}
            )
            available = spendable - due - settings.safe_buffer
            remaining = (
                max(1, (values["by_date"] - now.date()).days)
                if values["by_date"]
                else int(forecast[0].payload["days"])
            )
            after = available - requested
            verdict = (
                "comfortable"
                if after >= 5 * max(0, int(forecast[0].payload["daily_allowance_minor"]))
                else "tight"
                if after >= 0
                else "not_advised"
            )
            result = {
                "amount_minor": requested,
                "verdict": verdict,
                "available_minor": available,
                "after_purchase_minor": after,
                "buffer_minor": settings.safe_buffer,
                "upcoming_commitments_minor": due,
                "days_considered": remaining,
                "arithmetic": (
                    "current/wallet balance - upcoming recurring debits - "
                    "safe buffer - requested amount"
                ),
                "assumptions": ["No unrecorded bills or future income are included."],
            }
    return tool_input(name, result)["result"]
