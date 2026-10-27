"""Optional strict-JSON transaction classifier behind a provider boundary."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.ledger.normalise import FETCH_CATEGORIES, counterparty_key, narration_parts


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant: str = Field(min_length=1, max_length=100)
    category: str
    confidence: float = Field(ge=0, le=1)


class ClassifierProvider(Protocol):
    async def classify(self, narration: str) -> Classification: ...


class CachedClassifier:
    def __init__(self, provider: ClassifierProvider | None) -> None:
        self.provider = provider
        self.cache: dict[str, Classification] = {}

    async def classify(self, narration: str) -> Classification | None:
        key = counterparty_key(" ".join(narration_parts(narration)))
        if not key or self.provider is None:
            return None
        if key in self.cache:
            return self.cache[key]
        result = await self.provider.classify(narration)
        if result.category not in FETCH_CATEGORIES:
            return None
        self.cache[key] = result
        return result
