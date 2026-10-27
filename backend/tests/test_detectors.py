from datetime import UTC, datetime, timedelta

from app.insights.registry import run_all
from app.insights.types import Balance, LedgerView, Series, Settings, Tx

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)


def tx(i, days, amount, direction="debit", category="food", merchant="Chowdeck"):
    return Tx(str(i), NOW - timedelta(days=days), amount, direction, category, merchant)


def test_registry_has_twelve_detectors():
    from app.insights.registry import DETECTORS

    assert len(DETECTORS) == 12


def test_student_triggers_monopoly_velocity_and_opportunity():
    items = (
        tuple(tx(i, i, 300_000) for i in range(1, 12))
        + tuple(tx(f"old{i}", 30 + i, 150_000) for i in range(1, 40))
        + tuple(tx(f"inc{i}", i * 30, 2_000_000, "credit", "income", "Family") for i in range(3))
    )
    kinds = {
        x.kind
        for x in run_all(LedgerView(items, (Balance("a", 100_000, "wallet"),), ()), Settings(), NOW)
    }
    assert {"merchant_monopoly", "velocity_warning", "opportunity_cost_swap"} <= kinds


def test_not_enough_data_never_guesses():
    kinds = {x.kind for x in run_all(LedgerView(), Settings(), NOW)}
    assert not kinds


def test_bill_spike_near_miss():
    series = Series(
        "s", "Power", "utilities", 30, 100_000, 129_000, 100_000, 4, NOW + timedelta(days=4)
    )
    assert "bill_spike" not in {
        x.kind for x in run_all(LedgerView(recurring=(series,)), Settings(payday_hint=25), NOW)
    }


def test_subscription_and_price_change_trigger():
    s = Series(
        "s",
        "Spotify",
        "entertainment",
        30,
        100_000,
        106_000,
        100_000,
        4,
        NOW + timedelta(days=4),
        subscription_like=True,
    )
    kinds = {
        x.kind
        for x in run_all(
            LedgerView(balances=(Balance("a", 5_000_000, "current"),), recurring=(s,)),
            Settings(payday_hint=25),
            NOW,
        )
    }
    assert {"zombie_subscription", "renewal_countdown", "double_charge_price_change"} <= kinds
