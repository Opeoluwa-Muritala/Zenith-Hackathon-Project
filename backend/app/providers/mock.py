"""Deterministic offline provider used by tests and demo personas."""

from datetime import timedelta

from app.providers.base import AggregatorProvider, ProviderTransaction


class MockAggregatorProvider(AggregatorProvider):
    """Return deterministic Nigerian sample transactions."""

    async def transactions(self, account_id, start, end):
        return [
            ProviderTransaction(
                f"{account_id}-salary",
                end - timedelta(days=25),
                45_000_000,
                "credit",
                "NIP/ACME LTD/SALARY",
                "income",
                45_000_000,
            ),
            ProviderTransaction(
                f"{account_id}-netflix",
                end - timedelta(days=3),
                440_000,
                "debit",
                "POS NETFLIX.COM 00928",
                "entertainment",
                44_560_000,
            ),
        ]
