import pytest

from app.providers.base import ProviderError
from app.providers.statement import StatementUploadProvider


def test_valid_csv():
    rows = StatementUploadProvider().parse(
        b"date,amount_minor,direction,narration\n2026-01-01T00:00:00+00:00,100,debit,POS SHOP\n"
    )
    assert rows[0].amount_minor == 100


def test_rejects_oversized_upload():
    with pytest.raises(ProviderError):
        StatementUploadProvider().parse(b"x" * 2_000_001)


def test_rejects_negative_money():
    with pytest.raises(ProviderError):
        StatementUploadProvider().parse(
            b"date,amount_minor,direction,narration\n2026-01-01T00:00:00+00:00,-1,debit,x\n"
        )
