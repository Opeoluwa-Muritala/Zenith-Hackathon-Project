"""Verify that model text contains only figures present in supplied facts."""

import re
from typing import Any

NUMBER = re.compile(r"(?<![A-Za-z])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _normalise_number(token: str) -> str:
    value = token.replace(",", "").removesuffix("%")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value.lstrip("+")


def _fact_tokens(value: Any) -> tuple[set[str], set[str]]:
    numbers: set[str] = set()
    dates: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            child_numbers, child_dates = _fact_tokens(child)
            numbers |= child_numbers
            dates |= child_dates
    elif isinstance(value, (list, tuple)):
        for child in value:
            child_numbers, child_dates = _fact_tokens(child)
            numbers |= child_numbers
            dates |= child_dates
    elif isinstance(value, (str, int, float)):
        raw = str(value)
        dates |= set(ISO_DATE.findall(raw))
        raw = ISO_DATE.sub("", raw)
        numbers |= {_normalise_number(item) for item in NUMBER.findall(raw)}
    return numbers, dates


def verify_numbers(text: str, facts: Any) -> bool:
    """Return false if response adds a numeric token or ISO date absent from facts."""
    allowed_numbers, allowed_dates = _fact_tokens(facts)
    dates = ISO_DATE.findall(text)
    stripped = ISO_DATE.sub("", text)
    seen_numbers = {_normalise_number(item) for item in NUMBER.findall(stripped)}
    return set(dates) <= allowed_dates and seen_numbers <= allowed_numbers


def valid_output(text: str, facts: Any, *, max_length: int) -> bool:
    """Apply bounded non-empty copy rules and exact figure fidelity."""
    return bool(text.strip()) and len(text) <= max_length and verify_numbers(text, facts)
