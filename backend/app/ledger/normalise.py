import hashlib
import re

MERCHANTS = {
    "netflix": ("Netflix", "entertainment", True),
    "spotify": ("Spotify", "entertainment", True),
    "dstv": ("DStv", "utilities", True),
    "ikeja": ("Ikeja Electric", "utilities", False),
    "chowdeck": ("Chowdeck", "food", False),
    "salary": ("Employer", "income", False),
    "showmax": ("Showmax", "entertainment", True),
    "gym": ("Gym", "health", True),
    "cafe lagos": ("Cafe Lagos", "food", False),
    "friday dining": ("Friday Dining", "food", False),
    "living expense": ("Living Expense", "housing", False),
    "usd client": ("Client", "income", False),
    "family allowance": ("Family", "income", False),
}


def clean_narration(value):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .&-]", " ", value)).strip()[:200]


def categorise(value):
    lower = value.lower()
    for token, result in MERCHANTS.items():
        if token in lower:
            return result
    return ("Transfer", "transfers", False) if "nip" in lower else ("Other", "other", False)


def dedupe(account_id, external_id, posted_at, amount, direction):
    return hashlib.sha256(
        f"{account_id}|{external_id}|{posted_at.isoformat()}|{amount}|{direction}".encode()
    ).hexdigest()
