"""Allow-list model inputs so identifiers and raw ledger rows cannot escape."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict


class InsightPayloadForLLM(BaseModel):
    """Only the approved detector label and aggregate facts can reach wording."""

    model_config = ConfigDict(extra="ignore", strict=True)
    kind: str
    module: str
    facts: dict[str, Any]
    reference_title: str
    reference_body: str


class ToolResultForLLM(BaseModel):
    """Only a named, sanitised aggregate result can reach chat generation."""

    model_config = ConfigDict(extra="ignore", strict=True)
    name: str
    result: dict[str, Any]


SAFE_KEYS = frozenset(
    {
        "kind",
        "module",
        "merchant",
        "merchant_family",
        "category",
        "category_name",
        "amount_minor",
        "amount_minor_before",
        "amount_minor_after",
        "typical_amount_minor",
        "last_amount_minor",
        "previous_amount_minor",
        "monthly_amount_minor",
        "annualised_minor",
        "total_minor",
        "income_minor",
        "spend_minor",
        "balance_minor",
        "buffer_minor",
        "safe_to_spend_minor",
        "daily_allowance_minor",
        "monthly_income_minor",
        "monthly_spend_minor",
        "freed_monthly_minor",
        "annualised_total_minor",
        "projected_minor",
        "overshoot_minor",
        "surplus_minor",
        "foregone_interest_minor",
        "illustrated_interest_minor",
        "illustrated_12m_value_minor",
        "delta_minor",
        "percentage_jump",
        "share_bps",
        "savings_rate_bps",
        "rate_bps",
        "reduction_bps",
        "count",
        "cycles",
        "cadence_days",
        "days_until_income",
        "days_until_charge",
        "days",
        "period_days",
        "status",
        "verdict",
        "comfortable",
        "tight",
        "negative",
        "next_expected_at",
        "projected_crossover_date",
        "start_date",
        "end_date",
        "month",
        "weekday",
        "bucket",
        "charges",
        "items",
        "categories",
        "merchants",
        "months",
        "weeks",
        "assumptions",
        "arithmetic",
        "illustration",
        "disclaimer",
        "footer",
        "severity",
        "title",
        "body",
        "payload",
        "facts",
    }
)


def _money_display(key: str, value: int | float | str) -> str:
    """Render integer kobo as Naira for the model from deterministic values."""
    if key.endswith("_minor") and type(value) is int:
        sign = "-" if value < 0 else ""
        naira, kobo = divmod(abs(value), 100)
        return f"₦{sign}{naira:,}.{kobo:02d}"
    if key.endswith("_bps") and type(value) is int:
        return f"{value / 100:g}%"
    return str(value)


def sanitise(value: Any, *, key: str = "") -> Any:
    """Recursively retain allow-listed aggregate facts and discard all other fields."""
    if isinstance(value, dict):
        output = {}
        for child_key, child in value.items():
            if child_key in SAFE_KEYS:
                output[child_key] = sanitise(child, key=child_key)
        return output
    if isinstance(value, (list, tuple)):
        return [sanitise(item, key=key) for item in value[:25]]
    if type(value) is int and (key.endswith("_minor") or key.endswith("_bps")):
        return _money_display(key, value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:300] if isinstance(value, str) else value
    return None


def insight_input(kind: str, module: str, facts: dict, title: str, body: str) -> dict:
    """Validate one detector payload after stripping identifiers and raw text."""
    data = InsightPayloadForLLM(
        kind=kind,
        module=module,
        facts=sanitise(facts),
        reference_title=title[:160],
        reference_body=body[:280],
    )
    return data.model_dump()


def tool_input(name: str, result: dict) -> dict:
    """Validate a tool result after recursively applying the shared allow-list."""
    return ToolResultForLLM(name=name, result=sanitise(result)).model_dump()


def redact_user_text(value: str) -> str:
    """Mask obvious identity/contact strings before chat persistence or model calls."""
    value = re.sub(r"\b\d{11}\b", "[redacted number]", value)
    value = re.sub(r"\b\d{10}\b", "[redacted number]", value)
    value = re.sub(r"\+[1-9]\d{7,14}", "[redacted phone]", value)
    value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted email]", value)
    value = re.sub(r"\bmy name is\s+[^,.!?\n]{1,80}", "my name is [redacted]", value, flags=re.I)
    return value[:2000]
