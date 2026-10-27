"""Conservative institution classification using an auditable local mapping."""

import json
from pathlib import Path

from app.models import AccountCategory

MAPPING_PATH = Path(__file__).resolve().parent / "data" / "institution_categories.json"


def category_for_institution(code: str, name: str) -> tuple[AccountCategory, bool]:
    """Return category and whether the institution lacked an explicit mapping."""
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    category = mapping.get("codes", {}).get(code.strip().casefold())
    if category is None:
        category = mapping.get("names", {}).get(name.strip().casefold())
    if category is None:
        return AccountCategory.commercial_bank, True
    return AccountCategory(category), False
