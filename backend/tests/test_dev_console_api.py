from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main


class FakeDatabase:
    async def scalar(self, _statement):
        return "0026"


@pytest.mark.asyncio
async def test_dev_status_reports_readiness_without_secret_values(monkeypatch):
    monkeypatch.setattr(main.settings, "environment", "staging")
    monkeypatch.setattr(main.settings, "mono_secret_key", "test_connect")
    monkeypatch.setattr(main.settings, "mono_lookup_secret_key", "test_lookup")
    monkeypatch.setattr(main.settings, "webhook_secure_key", "configured")

    result = await main.dev_status(FakeDatabase())

    assert result["migration_revision"] == "0026"
    assert result["mono_sandbox_keys"] is True
    assert "mono_secret_key" not in result
    assert "webhook_secure_key" not in result


@pytest.mark.asyncio
async def test_dev_status_is_not_available_in_production(monkeypatch):
    monkeypatch.setattr(main.settings, "environment", "production")

    with pytest.raises(HTTPException) as error:
        await main.dev_status(SimpleNamespace())

    assert error.value.status_code == 404
