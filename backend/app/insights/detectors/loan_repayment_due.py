"""Upcoming confirmed or detected loan-repayment insight."""

from datetime import datetime

from app.insights.helpers import make
from app.insights.types import Insight, LedgerView, Settings


def detect(view: LedgerView, settings: Settings, now: datetime) -> list[Insight]:
    due = [item for item in view.obligations if 0 <= (item.due_date - now.date()).days <= 7]
    return [
        make(
            "cashflow",
            "loan_repayment_due",
            {
                "obligation_id": item.id,
                "lender": item.lender,
                "amount_minor": item.amount,
                "due_date": item.due_date.isoformat(),
                "transaction_ids": [],
                "confidence_bps": item.confidence_bps,
                "why_it_matters": "A scheduled repayment is due within seven days.",
                "action": "Confirm the due date and keep sufficient funds available.",
            },
            key=item.id,
            severity="warning",
        )
        for item in due
    ]
