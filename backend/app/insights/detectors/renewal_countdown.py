from app.insights.config import RENEWAL_DAYS
from app.insights.helpers import make, recent


def detect(view, settings, now):
    due = sorted(
        [
            s
            for s in view.recurring
            if s.status == "active"
            and 0 <= (s.next_expected_at.date() - now.date()).days <= RENEWAL_DAYS
        ],
        key=lambda s: s.next_expected_at,
    )
    if not due:
        return []
    total = sum(s.last_amount for s in due)
    bal = sum(b.amount for b in view.balances if b.account_type in {"current", "wallet"})
    income = sum(t.amount for t in recent(view, now, 30, "credit"))
    return [
        make(
            "leaks",
            "renewal_countdown",
            {
                "count": len(due),
                "days": [(s.next_expected_at.date() - now.date()).days for s in due],
                "total_minor": total,
                "balance_share_bps": total * 10000 // bal if bal else None,
                "income_share_bps": total * 10000 // income if income else None,
            },
        )
    ]
