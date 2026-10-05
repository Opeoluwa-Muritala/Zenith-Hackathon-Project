"""Provider boundary that keeps bank APIs out of domain code."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProviderTransaction:
    external_id: str
    posted_at: datetime
    amount_minor: int
    direction: str
    narration: str
    category: str | None
    balance_after_minor: int | None


class ProviderError(RuntimeError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class ProviderNotReady(ProviderError):
    pass


class AggregatorProvider(ABC):
    """Fetch account data only after the caller validates active consent."""

    @abstractmethod
    async def transactions(
        self, account_id: str, start: datetime, end: datetime
    ) -> list[ProviderTransaction]: ...
    async def unlink(self, account_id: str) -> None:
        return None
