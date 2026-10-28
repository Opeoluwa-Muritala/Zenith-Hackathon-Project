"""SME transaction-use suggestions and owner review lifecycle."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.ledger.normalise import category_label
from app.models import Transaction

UseLabel = Literal["business", "personal", "unsure"]

BUSINESS_CATEGORIES = {"Bills & Utilities"}
PERSONAL_CATEGORIES = {"Food & Dining", "Airtime & Data"}


class ModeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["consumer", "sme"]


class UseReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: UseLabel


def suggest_use(transaction: Transaction) -> tuple[UseLabel, int]:
    """Conservative category-based suggestion; ambiguity remains visibly unsure."""
    category = category_label(transaction.category)
    merchant = (transaction.decoded_merchant or "").lower()
    if any(token in merchant for token in ("tax", "vat", "fee", "maintenance")):
        return "business", 8500
    if category in BUSINESS_CATEGORIES:
        return "business", 8000
    if category in PERSONAL_CATEGORIES:
        return "personal", 8000
    return "unsure", 4000


def label_out(
    transaction: Transaction,
    suggested: UseLabel,
    confidence_bps: int,
    confirmed: str | None,
    updated_at: datetime,
) -> dict:
    return {
        "transaction_id": transaction.id,
        "amount_minor": transaction.amount_minor,
        "posted_at": transaction.posted_at,
        "suggested_label": suggested,
        "confidence_bps": confidence_bps,
        "confirmed_label": confirmed,
        "effective_label": confirmed or suggested,
        "updated_at": updated_at,
    }
