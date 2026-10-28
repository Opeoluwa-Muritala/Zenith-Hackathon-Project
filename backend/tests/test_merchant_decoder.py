"""Narration formats and category fallback use synthetic financial data."""

import pytest

from app.ledger.normalise import categorise, narration_parts


@pytest.mark.parametrize(
    "narration,merchant,category",
    [
        ("NIP/POS/FLUTTERWAVE/CHOWDECK/REF123456", "Chowdeck", "Food & Dining"),
        ("WEB/PAYSTACK/NETFLIX.COM/0000000000", "Netflix", "Bills & Utilities"),
        ("USSD/MTN/AIRTIME", "MTN", "Airtime & Data"),
        ("POS UBER 1234567890", "Uber", "Transport"),
        ("NIP//FROM//DEMO PERSON//0000000000", "DEMO PERSON", "Uncategorised"),
    ],
)
def test_narration_decoding(narration, merchant, category):
    assert categorise(narration)[:2] == (merchant, category)
    assert "0000000000" not in " ".join(narration_parts(narration))


def test_merchant_category_precedes_provider_category():
    assert categorise("POS CHOWDECK", "transport")[1] == "Food & Dining"
    assert categorise("POS DEMO MERCHANT", "transport")[1] == "Transport"
    assert categorise("POS DEMO MERCHANT", "unknown")[1] == "Uncategorised"
