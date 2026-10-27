"""One cache freshness convention for list, detail and refresh responses."""

from app.ledger.service import as_utc
from app.models import SyncStatus


def balance_state(account, now, stale_minutes):
    age = (
        max(0, int((now - as_utc(account.balance_synced_at)).total_seconds() // 60))
        if account.balance_synced_at
        else None
    )
    delayed = account.sync_status != SyncStatus.ok or age is None or age >= stale_minutes
    message = "Balance not synced yet" if age is None else f"Balance synced {age}m ago"
    if account.sync_paused:
        message = "Sync paused; " + message.lower()
    elif delayed:
        message = "Updates delayed; " + message.lower()
    return {
        "balance_minor": account.current_balance_minor,
        "balance_synced_at": account.balance_synced_at,
        "cache_age_minutes": age,
        "sync_status": "delayed" if delayed else "ok",
        "sync_message": message,
    }
