"""Authenticated field encryption for reversible sensitive values."""

# TODO(security): evaluate minimising account.account_number_masked and raw
# transaction narrations; they are stored in plaintext today.

import hashlib
import json
import re
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_development_key = Fernet.generate_key()
_MONO_DERIVED_KEY_ID = "mono_derived_v1"


def _mono_derived_key() -> str:
    secret = get_settings().mono_secret_key
    if len(secret) < 24 or secret.startswith("REPLACE_"):
        raise RuntimeError("A configured Mono secret is required for derived field encryption")
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"fetch-field-encryption-v1",
        info=b"mono-secret-to-field-key",
    ).derive(secret.encode())
    return urlsafe_b64encode(key).decode()


def _fernet(key_id: str | None = None) -> Fernet:
    settings = get_settings()
    key = settings.field_encryption_key
    if key_id == _MONO_DERIVED_KEY_ID:
        previous = json.loads(settings.field_encryption_previous_keys)
        key = previous.get(key_id) or _mono_derived_key()
    elif key_id and key_id != settings.field_encryption_key_id:
        try:
            key = json.loads(settings.field_encryption_previous_keys)[key_id]
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("Unknown field encryption key id") from exc
    if not key:
        if settings.mono_secret_key:
            key = _mono_derived_key()
        elif settings.environment == "production" or settings.demo_mode:
            raise RuntimeError("A stable field encryption key is required")
        else:
            key = _development_key.decode()
    return Fernet(key.encode())


def encrypt_field(value: str) -> str:
    settings = get_settings()
    key_id = (
        settings.field_encryption_key_id
        if settings.field_encryption_key or not settings.mono_secret_key
        else _MONO_DERIVED_KEY_ID
    )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", key_id):
        raise RuntimeError("Invalid field encryption key id")
    if settings.field_encryption_key and key_id == _MONO_DERIVED_KEY_ID:
        raise RuntimeError("Reserved field encryption key id")
    return f"v1:{key_id}:{_fernet(key_id).encrypt(value.encode()).decode()}"


def decrypt_field(value: str) -> str:
    if value.startswith("v1:"):
        _, key_id, ciphertext = value.split(":", 2)
        return _fernet(key_id).decrypt(ciphertext.encode()).decode()
    return _fernet().decrypt(value.encode()).decode()


def hash_field(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
