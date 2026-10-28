"""Durable unlink and complete user-data purge primitives."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.encryption import decrypt_field
from app.core.security import hash_secret
from app.identity.audit import subject_hash
from app.models import (
    Account,
    AuthLockout,
    BookkeeperInvite,
    ManualAsset,
    OtpCode,
    PendingUnlink,
    ProviderLink,
    SecurityAuditEvent,
    Transaction,
    User,
    WipeAudit,
)
from app.providers.base import ProviderError
from app.providers.mono import MonoProvider

# Every direct FK to users must be classified here. The metadata test deliberately fails when
# a later migration adds another direct reference without updating the wipe design.
PURGE_USER_FOREIGN_KEYS = {
    "accounts.user_id",
    "ai_audit.user_id",
    "assistant_conversations.user_id",
    "bookkeeper_invites.accepted_by_user_id",
    "bookkeeper_invites.owner_user_id",
    "budgets.user_id",
    "bvn_lookup_sessions.user_id",
    "category_rules.user_id",
    "classification_corrections.user_id",
    "consents.user_id",
    "device_tokens.user_id",
    "discovered_accounts.user_id",
    "insight_alerts.user_id",
    "insight_profiles.user_id",
    "insights.user_id",
    "manual_assets.user_id",
    "notification_logs.user_id",
    "notification_preferences.user_id",
    "obligations.user_id",
    "provider_call_logs.user_id",
    "provider_links.user_id",
    "recurring_series.user_id",
    "refresh_tokens.user_id",
    "report_share_links.user_id",
    "security_audit_events.user_id",
    "transaction_use_labels.user_id",
    "transfer_suggestions.user_id",
    "user_settings.user_id",
}


def wipe_user_hash(user_id: UUID) -> str:
    settings = get_settings()
    pepper = settings.otp_secret or settings.bvn_pepper
    return hash_secret(str(user_id), pepper)


async def queue_provider_link(db: AsyncSession, link: ProviderLink) -> PendingUnlink | None:
    if not link.provider_account_id_encrypted or not link.provider_account_id_hash:
        return None
    existing = await db.scalar(
        select(PendingUnlink).where(
            PendingUnlink.provider == link.provider,
            PendingUnlink.provider_account_id_hash == link.provider_account_id_hash,
        )
    )
    if existing is not None:
        return existing
    row = PendingUnlink(
        user_hash=wipe_user_hash(link.user_id),
        provider=link.provider,
        provider_account_id_encrypted=link.provider_account_id_encrypted,
        provider_account_id_hash=link.provider_account_id_hash,
        attempts=0,
        created_at=now_utc(),
    )
    db.add(row)
    await db.flush()
    return row


async def retry_pending_unlink(db: AsyncSession, row: PendingUnlink) -> bool:
    if row.completed_at is not None:
        return True
    row.attempts += 1
    row.last_attempt_at = now_utc()
    try:
        identifier = decrypt_field(row.provider_account_id_encrypted)
        if row.provider != "mono":
            raise ValueError("Unsupported unlink provider")
        settings = get_settings()
        await MonoProvider(settings.mono_secret_key, settings.mono_base_url).unlink(identifier)
    except (ProviderError, ValueError):
        return False
    row.completed_at = now_utc()
    links = (
        await db.scalars(
            select(ProviderLink).where(
                ProviderLink.provider == row.provider,
                ProviderLink.provider_account_id_hash == row.provider_account_id_hash,
            )
        )
    ).all()
    for link in links:
        link.status = "unlinked"
        link.provider_account_id = None
    return True


async def wipe_counts(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    account_ids = select(Account.id).where(Account.user_id == user_id)
    return {
        "accounts": int(
            await db.scalar(select(func.count()).where(Account.user_id == user_id)) or 0
        ),
        "transactions": int(
            await db.scalar(select(func.count()).where(Transaction.account_id.in_(account_ids)))
            or 0
        ),
        "manual_assets": int(
            await db.scalar(select(func.count()).where(ManualAsset.user_id == user_id)) or 0
        ),
    }


async def purge_user(db: AsyncSession, user: User, wiped_at: datetime) -> dict[str, int]:
    """Delete one user and all owned rows in the current database transaction."""
    counts = await wipe_counts(db, user.id)
    user_hash = wipe_user_hash(user.id)
    identifier = user.phone or user.email
    identifier_digest = subject_hash(identifier) if identifier else None
    # These records are not all owned through a cascading user FK, so purge them explicitly.
    if identifier:
        await db.execute(delete(OtpCode).where(OtpCode.identifier == identifier))
        await db.execute(
            delete(AuthLockout).where(AuthLockout.identifier_hash == identifier_digest)
        )
    audit_filter = SecurityAuditEvent.user_id == user.id
    if identifier_digest is not None:
        audit_filter = audit_filter | (SecurityAuditEvent.subject_hash == identifier_digest)
    await db.execute(delete(SecurityAuditEvent).where(audit_filter))
    await db.execute(
        delete(BookkeeperInvite).where(BookkeeperInvite.accepted_by_user_id == user.id)
    )
    managed_user = await db.get(User, user.id)
    if managed_user is None:
        raise RuntimeError("User disappeared during wipe")
    await db.delete(managed_user)
    await db.flush()
    db.add(WipeAudit(user_hash=user_hash, wiped_at=wiped_at))
    return counts
