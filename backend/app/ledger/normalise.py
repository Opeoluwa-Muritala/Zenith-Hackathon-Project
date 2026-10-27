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

NIGERIA_RULES = (
    (re.compile(r"\b(?:sms|alert)\s*(?:fee|charge)\b", re.I), "SMS Alert Fee", "Bills & Utilities"),
    (re.compile(r"\b(?:stamp\s*duty|stamping)\b", re.I), "Stamp Duty", "Bills & Utilities"),
    (re.compile(r"\bvat\b", re.I), "VAT", "Bills & Utilities"),
    (re.compile(r"\b(?:tax|wht|withholding|paye|cit|stamp)\s*(?:payment|remittance|deduction)?\b", re.I), "Tax", "Bills & Utilities"),
    (re.compile(r"\bmaintenance\s*(?:fee|charge)?\b", re.I), "Account Maintenance Fee", "Bills & Utilities"),
    (re.compile(r"\b(?:card|atm)\s*(?:fee|charge)\b", re.I), "Card Fee", "Bills & Utilities"),
    (re.compile(r"\b(?:ussd|nip|pos|transfer)\s*(?:fee|charge)\b", re.I), "Bank Service Fee", "Bills & Utilities"),
    (re.compile(r"\b(?:airtime|data)\b", re.I), "Airtime & Data", "Airtime & Data"),
)


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
    for pattern, merchant, category in NIGERIA_RULES:
        if merchant == "Airtime & Data":
            continue
        if pattern.search(lower):
            return merchant, category, False
    lender = lender_name(value)
    if lender:
        return lender, "Bills & Utilities", True
    for merchant in merchant_aliases():
        if any(
            re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lower)
            for alias in merchant["aliases"]
        ):
            return merchant["name"], merchant["category"], merchant["subscription"]
    if re.search(r"\b(?:airtime|data)\b", lower):
        return (" ".join(narration_parts(value))[:100] or "Airtime & Data", "Airtime & Data", False)
    try:
        from rapidfuzz import fuzz

        candidate = counterparty_key(" ".join(narration_parts(value)))
        best = max(merchant_aliases(), key=lambda item: max(fuzz.ratio(candidate, counterparty_key(alias)) for alias in item["aliases"]), default=None)
        if best and max(fuzz.ratio(candidate, counterparty_key(alias)) for alias in best["aliases"]) >= 90:
            return best["name"], best["category"], best["subscription"]
    except ImportError:
        pass
    name = " ".join(narration_parts(value))[:100] or "Other"
    category = category_label(provider_category)
    return name, category, False


def dedupe(account_id, external_id, posted_at, amount, direction):
    return hashlib.sha256(
        f"{account_id}|{external_id}|{posted_at.isoformat()}|{amount}|{direction}".encode()
    ).hexdigest()
