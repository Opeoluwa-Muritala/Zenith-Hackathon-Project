"""The demo must distinguish fresh cache, delayed updates and paused sync."""

from datetime import UTC, datetime, timedelta

from app.ledger.balances import balance_state
from app.models import Account, SyncStatus


def test_balance_freshness_boundary_and_paused_message():
    now = datetime(2026, 10, 13, tzinfo=UTC)
    account = Account(
        current_balance_minor=1200,
        balance_synced_at=now - timedelta(minutes=44),
        sync_status=SyncStatus.ok,
        sync_paused=False,
    )
    assert balance_state(account, now, 45)["sync_status"] == "ok"
    account.balance_synced_at -= timedelta(minutes=1)
    state = balance_state(account, now, 45)
    assert state["sync_status"] == "delayed"
    assert "45m ago" in state["sync_message"]
    account.sync_paused = True
    assert balance_state(account, now, 45)["sync_message"].startswith("Sync paused")
    account.balance_synced_at = None
    assert balance_state(account, now, 45)["cache_age_minutes"] is None
