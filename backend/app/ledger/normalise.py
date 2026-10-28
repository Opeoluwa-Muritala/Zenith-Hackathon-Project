import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

CATEGORY_ALIASES = {
    "food": "Food & Dining",
    "food and dining": "Food & Dining",
    "utilities": "Bills & Utilities",
    "bills": "Bills & Utilities",
    "entertainment": "Bills & Utilities",
    "housing": "Bills & Utilities",
    "transport": "Transport",
    "airtime": "Airtime & Data",
    "data": "Airtime & Data",
    "shopping": "Shopping & Transfers",
    "health": "Shopping & Transfers",
    "transfers": "Transfers & Family",
    "transfer": "Transfers & Family",
}
FETCH_CATEGORIES = {
    "Food & Dining",
    "Bills & Utilities",
    "Transport",
    "Airtime & Data",
    "Shopping & Transfers",
    "Transfers & Family",
    "Uncategorised",
}


def category_label(value: str | None) -> str:
    if value in FETCH_CATEGORIES:
        return value
    return CATEGORY_ALIASES.get((value or "").strip().lower(), "Uncategorised")


@lru_cache
def merchant_aliases() -> list[dict]:
    return json.loads(
        (Path(__file__).parent / "data" / "merchants.json").read_text(encoding="utf-8")
    )


def narration_parts(value: str) -> list[str]:
    """Split provider formats; remove channel, processor and reference components."""
    parts = re.split(r"[/|:]+", value)
    cleaned = []
    for part in parts:
        part = re.sub(r"\b(?:REF|SESSION|RRN|STAN)[A-Z0-9_-]*\b", " ", part, flags=re.I)
        part = re.sub(r"\b[0-9]{5,}\b", " ", part)
        part = re.sub(
            r"\b(?:NIP|POS|WEB|USSD|TRF|TRANSFER|FROM|TO|DEBIT|CREDIT|FLUTTERWAVE|PAYSTACK)\b",
            " ",
            part,
            flags=re.I,
        )
        part = clean_narration(part)
        if part:
            cleaned.append(part)
    return cleaned


def clean_narration(value):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .&-]", " ", value)).strip()[:200]


def counterparty_key(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", value.lower())).strip()[:160]


@lru_cache
def lender_aliases() -> list[dict]:
    source = Path(__file__).parent / "data" / "lenders.json"
    return json.loads(source.read_text(encoding="utf-8"))


def lender_name(value: str) -> str | None:
    lower = value.lower()
    for lender in lender_aliases():
        if any(alias in lower for alias in lender["aliases"]):
            return lender["name"]
    return None


def categorise(value, provider_category=None):
    lower = value.lower()
    lender = lender_name(value)
    if lender:
        return lender, "Bills & Utilities", True
    for merchant in merchant_aliases():
        if any(
            re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lower)
            for alias in merchant["aliases"]
        ):
            return merchant["name"], merchant["category"], merchant["subscription"]
    name = " ".join(narration_parts(value))[:100] or "Other"
    category = category_label(provider_category)
    return name, category, False


def dedupe(account_id, external_id, posted_at, amount, direction):
    return hashlib.sha256(
        f"{account_id}|{external_id}|{posted_at.isoformat()}|{amount}|{direction}".encode()
    ).hexdigest()
