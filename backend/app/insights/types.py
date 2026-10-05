"""Database-independent detector values; all money is integer kobo."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Tx:
    id: str
    posted_at: datetime
    amount: int
    direction: str
    category: str
    merchant: str = ""
    subscription_like: bool = False
    legitimately_repeating: bool = False


@dataclass(frozen=True)
class Balance:
    account_id: str
    amount: int
    account_type: str
    savings_rate_bps: int = 0
    last_movement_at: datetime | None = None


@dataclass(frozen=True)
class Series:
    id: str
    merchant: str
    category: str
    cadence_days: int
    typical_amount: int
    last_amount: int
    previous_amount: int | None
    cycles: int
    next_expected_at: datetime
    status: str = "active"
    subscription_like: bool = False
    direction: str = "debit"


@dataclass(frozen=True)
class Settings:
    safe_buffer: int = 0
    payday_hint: int | None = None
    discretionary: tuple[str, ...] = ("food", "shopping", "entertainment", "transport")
    nominal_tbill_rate_bps: int = 1500


@dataclass(frozen=True)
class LedgerView:
    transactions: tuple[Tx, ...] = ()
    balances: tuple[Balance, ...] = ()
    recurring: tuple[Series, ...] = ()


@dataclass(frozen=True)
class Insight:
    module: str
    kind: str
    severity: str
    payload: dict
    dedupe_key: str
