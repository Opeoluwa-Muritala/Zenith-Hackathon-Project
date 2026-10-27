import pytest
from pydantic import ValidationError

from app.ledger.classifier import CachedClassifier, Classification


class FakeClassifier:
    calls = 0

    async def classify(self, narration):
        self.calls += 1
        return Classification(merchant="Unknown Shop", category="Shopping & Transfers", confidence=0.8)


@pytest.mark.asyncio
async def test_NDL_7_strict_json_classifier_is_cached_by_normalised_narration():
    provider = FakeClassifier()
    classifier = CachedClassifier(provider)
    first = await classifier.classify("NIP/REF12345/UNKNOWN SHOP")
    second = await classifier.classify("unknown shop")
    assert first == second
    assert provider.calls == 1


def test_NDL_7_classifier_rejects_extra_fields_and_invalid_categories():
    with pytest.raises(ValidationError):
        Classification(merchant="x", category="Food & Dining", confidence=0.5, raw="secret")
