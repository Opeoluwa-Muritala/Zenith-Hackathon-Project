"""Local purge and durable remote-unlink state transitions."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.models import (
    Account,
    AiAudit,
    AssistantConversation,
    AssistantMessage,
    Consent,
    ConsentAudit,
    InsightRecord,
    Obligation,
    ObligationPayment,
    PendingUnlink,
    ProviderLink,
    RecurringSeries,
    Transaction,
)
from app.privacy.service import queue_provider_link
from app.providers.base import ProviderError
from app.providers.mono import MonoProvider


async def purge_linked_account(db: AsyncSession, account: Account, link: ProviderLink) -> None:
    """Remove account data atomically while retaining only encrypted ID for retry."""
    await queue_provider_link(db, link)
    obligations = select(Obligation.id).where(Obligation.account_id == account.id)
    await db.execute(
        delete(ObligationPayment).where(ObligationPayment.obligation_id.in_(obligations))
    )
    await db.execute(delete(Obligation).where(Obligation.account_id == account.id))
    await db.execute(delete(RecurringSeries).where(RecurringSeries.account_id == account.id))
    await db.execute(delete(Transaction).where(Transaction.account_id == account.id))
    await db.execute(
        delete(Account).where(Account.id == account.id, Account.user_id == account.user_id)
    )
    conversations = select(AssistantConversation.id).where(
        AssistantConversation.user_id == account.user_id
    )
    await db.execute(
        delete(AssistantMessage).where(AssistantMessage.conversation_id.in_(conversations))
    )
    await db.execute(
        delete(AssistantConversation).where(AssistantConversation.user_id == account.user_id)
    )
    await db.execute(delete(AiAudit).where(AiAudit.user_id == account.user_id))
    await db.execute(delete(InsightRecord).where(InsightRecord.user_id == account.user_id))
    consent = await db.get(Consent, link.consent_id)
    if consent and consent.revoked_at is None:
        consent.revoked_at = now_utc()
        db.add(
            ConsentAudit(
                consent_id=consent.id,
                event="revoked",
                actor=str(account.user_id),
                at=consent.revoked_at,
            )
        )
    link.status = (
        "pending_unlink" if link.provider == "mono" and link.provider_account_id else "unlinked"
    )
    if link.status == "unlinked":
        link.provider_account_id = None


async def retry_pending_link(db: AsyncSession, link: ProviderLink) -> bool:
    """Return true only when Mono confirmed unlink; preserve ciphertext on failure."""
    if link.status != "pending_unlink":
        return link.status == "unlinked"
    identifier = link.provider_account_id
    if not identifier:
        link.status = "unlinked"
        return True
    settings = get_settings()
    try:
        await MonoProvider(settings.mono_secret_key, settings.mono_base_url).unlink(identifier)
    except (ProviderError, ValueError):
        return False
    queued = await db.scalar(
        select(PendingUnlink).where(
            PendingUnlink.provider == link.provider,
            PendingUnlink.provider_account_id_hash == link.provider_account_id_hash,
        )
    )
    if queued is not None:
        queued.attempts += 1
        queued.last_attempt_at = now_utc()
        queued.completed_at = now_utc()
    link.status = "unlinked"
    link.provider_account_id = None
    return True
