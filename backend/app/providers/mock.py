"""Deterministic offline provider used by tests and demo personas."""

from datetime import datetime, timedelta
from random import Random

from app.providers.base import AggregatorProvider, ProviderTransaction


class MockAggregatorProvider(AggregatorProvider):
    """Return deterministic Nigerian sample transactions."""

    async def transactions(self, account_id, start, end):
        persona = account_id.split(":", 1)[0]
        if persona not in {"salaried", "freelancer", "student"}:
            return []
        rng = Random(20261005 + {"salaried": 1, "freelancer": 2, "student": 3}[persona])
        rows = []

        def add(key, date, amount, direction, narration):
            posted = datetime(date.year, date.month, date.day, 12, tzinfo=end.tzinfo)
            if start <= posted <= end:
                rows.append(
                    ProviderTransaction(
                        f"{account_id}:{key}", posted, amount, direction, narration, None, None
                    )
                )

        for month in range(6):
            anchor = end - timedelta(days=30 * month)
            first = anchor - timedelta(days=anchor.day - 1)
            if persona == "salaried":
                add(f"salary-{month}", first, 60_000_000, "credit", "NIP//ACME LTD//SALARY")
                add(
                    f"netflix-{month}",
                    first + timedelta(days=3),
                    440_000,
                    "debit",
                    "POS NETFLIX.COM 00928",
                )
                add(
                    f"dstv-{month}",
                    first + timedelta(days=4),
                    800_000,
                    "debit",
                    "USSD DSTV SUBSCRIPTION",
                )
                add(
                    f"power-{month}",
                    first + timedelta(days=3),
                    2_400_000 if month == 0 else 1_000_000,
                    "debit",
                    "NIP IKEJA ELECTRIC TOKEN",
                )
                if month >= 3:
                    add(
                        f"gym-{month}",
                        first + timedelta(days=7),
                        1_200_000,
                        "debit",
                        "POS GYM MEMBERSHIP",
                    )
            elif persona == "freelancer":
                add(
                    f"inflow-{month}",
                    first + timedelta(days=1),
                    5_000_000 if month < 2 else 12_000_000,
                    "credit",
                    "NIP USD CLIENT SETTLEMENT",
                )
                if month > 0:
                    for name, amount, day in (
                        ("NETFLIX", 440_000, 17),
                        ("SPOTIFY", 630_000 if month == 1 else 550_000, 18),
                        ("SHOWMAX", 420_000, 19),
                    ):
                        add(
                            f"{name}-{month}",
                            first + timedelta(days=day),
                            amount,
                            "debit",
                            f"POS {name} SUBSCRIPTION",
                        )
                add(
                    f"living-{month}",
                    first + timedelta(days=14),
                    7_000_000,
                    "debit",
                    "NIP LIVING EXPENSE",
                )
            else:
                add(f"allowance-{month}", first, 2_000_000, "credit", "NIP FAMILY ALLOWANCE")
                for index in range(8):
                    add(
                        f"food-{month}-{index}",
                        first + timedelta(days=1 + index * 3),
                        250_000 + rng.randrange(30_000),
                        "debit",
                        "POS CHOWDECK ORDER",
                    )
        if persona == "salaried":
            for week in range(22):
                day = end - timedelta(days=7 * week)
                friday = day - timedelta(days=(day.weekday() - 4) % 7)
                add(f"friday-{week}", friday, 900_000, "debit", "POS FRIDAY DINING")
        if persona == "freelancer":
            add("duplicate-a", end - timedelta(days=2), 230_000, "debit", "POS CAFE LAGOS")
            add("duplicate-b", end - timedelta(days=2), 230_000, "debit", "POS CAFE LAGOS")
        return rows
