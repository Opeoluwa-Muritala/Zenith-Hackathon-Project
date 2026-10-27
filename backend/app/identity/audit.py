"""Append-only, metadata-only authentication audit events."""

import hashlib
import hmac
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.models import SecurityAuditEvent


def subject_hash(identifier: str) -> str:
    """Create a non-reversible correlation key without persisting an identifier."""
    secret = get_settings().otp_secret
    if not secret:
        secret = get_settings().jwt_secret
    return hmac.new(secret.encode(), identifier.encode(), hashlib.sha256).hexdigest()


def record_auth_event(
    db: AsyncSession, event: str, *, user_id: UUID | None = None, identifier: str | None = None
) -> None:
    db.add(
        SecurityAuditEvent(
            user_id=user_id,
            event=event,
            subject_hash=subject_hash(identifier) if identifier else None,
            occurred_at=now_utc(),
        )
    )
