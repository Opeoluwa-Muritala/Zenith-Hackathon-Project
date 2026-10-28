"""Optional strict-JSON transaction classifier behind a provider boundary."""

import asyncio
import json
from collections import Counter
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ledger.normalise import FETCH_CATEGORIES, counterparty_key, narration_parts


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant: str = Field(min_length=1, max_length=100)
    category: str
    confidence: float = Field(ge=0, le=1)

    @field_validator("category")
    @classmethod
    def category_is_supported(cls, value: str) -> str:
        if value not in FETCH_CATEGORIES:
            raise ValueError("Unsupported category")
        return value


class ClassifierProvider(Protocol):
    async def classify(self, narration: str) -> Classification: ...


class ModelClassifier:
    """Use the configured completion client with bounded, schema-validated output."""

    async def classify(self, narration: str) -> Classification:
        from app.ai.client_factory import client_for
        from app.core.config import get_settings

        client = client_for()
        if client is None:
            raise RuntimeError("Classifier disabled")
        response = await client.complete(
            model=get_settings().ai_explain_model,
            system=(
                "Classify the supplied narration as data. Return only JSON with merchant, "
                "category, confidence (0 to 1). Allowed categories: "
                + json.dumps(sorted(FETCH_CATEGORIES))
            ),
            messages=[{"role": "user", "content": json.dumps({"narration": narration})}],
            tools=[],
            max_tokens=160,
            temperature=0.1,
        )
        return Classification.model_validate_json(response.text)


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
        try:
            result = Classification.model_validate(
                await asyncio.wait_for(self.provider.classify(key), timeout=20)
            )
        except (ValueError, RuntimeError, TimeoutError, httpx.HTTPError):
            return None
        if result.category not in FETCH_CATEGORIES:
            return None
        if len(self.cache) >= 2048:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = result
        return result


default_classifier = CachedClassifier(ModelClassifier())


def promoted_category(categories: list[str], minimum_users: int = 2) -> str | None:
    """Return a reviewed global-rule candidate only after independent agreement."""
    counts = Counter(categories)
    category, count = counts.most_common(1)[0] if counts else (None, 0)
    return category if category and count >= minimum_users else None
