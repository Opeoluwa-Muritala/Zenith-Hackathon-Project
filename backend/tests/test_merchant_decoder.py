"""Narration formats and category fallback use synthetic financial data."""

from datetime import UTC, datetime, timedelta

import pytest

from app.ledger.normalise import (
    categorise,
    detect_ajo_esusu,
    narration_parts,
    suggest_family_transfer,
)


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


def test_NDL_2_nigerian_fee_rules_are_deterministic():
    assert categorise("NIP TRANSFER FEE")[:2] == ("Bank Service Fee", "Bills & Utilities")
    assert categorise("SMS ALERT CHARGE")[:2] == ("SMS Alert Fee", "Bills & Utilities")
    assert categorise("WHT TAX REMITTANCE")[:2] == ("Tax", "Bills & Utilities")


def test_NDL_5_NDL_6_family_and_ajo_are_suggestions_until_confirmed():
    assert suggest_family_transfer(["NIP TO AMAKA", "NIP TO AMAKA"])
    assert not suggest_family_transfer(["NIP TO AMAKA"])
    day = datetime(2026, 1, 1, tzinfo=UTC)
    debits = [(day + timedelta(days=7 * index), 10_000, "AMAKA") for index in range(3)]
    credits = [(day + timedelta(days=30), 50_000, "AMAKA")]
    assert detect_ajo_esusu(debits, credits) == "amaka"
    assert categorise("AIRTIME PURCHASE")[1] == "Airtime & Data"
