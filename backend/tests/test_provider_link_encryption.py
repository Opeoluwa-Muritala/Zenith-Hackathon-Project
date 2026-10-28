"""Provider account IDs are reversible for API calls but never stored as plaintext."""

import json
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.encryption import decrypt_field, encrypt_field, hash_field
from app.models import ProviderLink


def test_provider_account_id_is_encrypted_and_searchable():
    identifier = "acc_fake_identifier_123"
    link = ProviderLink(
        user_id=uuid4(),
        consent_id=uuid4(),
        provider="mono",
        provider_account_id=identifier,
    )
    assert identifier not in link.provider_account_id_encrypted
    assert link.provider_account_id_hash == hash_field(identifier)
    assert link.provider_account_id == identifier
    link.provider_account_id = None
    assert link.provider_account_id_encrypted is None
    assert link.provider_account_id_hash is None


def test_field_encryption_key_rotation(monkeypatch):
    settings = get_settings()
    original_key = Fernet.generate_key().decode()
    next_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "field_encryption_key_id", "old")
    monkeypatch.setattr(settings, "field_encryption_key", original_key)
    ciphertext = encrypt_field("fake-sensitive-value")
    assert ciphertext.startswith("v1:old:")
    monkeypatch.setattr(settings, "field_encryption_key_id", "current")
    monkeypatch.setattr(settings, "field_encryption_key", next_key)
    monkeypatch.setattr(
        settings, "field_encryption_previous_keys", json.dumps({"old": original_key})
    )
    assert decrypt_field(ciphertext) == "fake-sensitive-value"
    assert decrypt_field(encrypt_field("another-fake-value")) == "another-fake-value"


def test_mono_derived_key_is_stable_and_survives_dedicated_key_rotation(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "field_encryption_key", "")
    monkeypatch.setattr(settings, "mono_secret_key", "fake-mono-secret-for-derivation-123456")
    ciphertext = encrypt_field("fake-account-identifier")
    assert ciphertext.startswith("v1:mono_derived_v1:")
    assert "fake-account-identifier" not in ciphertext
    assert decrypt_field(ciphertext) == "fake-account-identifier"

    monkeypatch.setattr(settings, "field_encryption_key", Fernet.generate_key().decode())
    assert decrypt_field(ciphertext) == "fake-account-identifier"


def test_mono_derived_key_requires_existing_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "field_encryption_key", "")
    monkeypatch.setattr(settings, "mono_secret_key", "REPLACE_MONO_KEY")
    monkeypatch.setattr(settings, "demo_mode", True)
    with pytest.raises(RuntimeError, match="configured Mono secret"):
        decrypt_field("v1:mono_derived_v1:fake-ciphertext")
