"""Idempotent per-device push delivery with invalid-token handling."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.encryption import decrypt_field
from app.models import DeviceToken, NotificationLog
from app.notifications.push import PushProvider


async def send_notification(
    db: AsyncSession,
    provider: PushProvider,
    *,
    user_id: UUID,
    event_key: str,
    kind: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send once per valid device; failed/disabled attempts remain retryable."""
    devices = (
        await db.scalars(
            select(DeviceToken).where(
                DeviceToken.user_id == user_id,
                DeviceToken.is_valid.is_(True),
            )
        )
    ).all()
    sent = 0
    for device in devices:
        log = await db.scalar(
            select(NotificationLog).where(
                NotificationLog.device_id == device.id,
                NotificationLog.event_key == event_key,
            )
        )
        attempt_time = now_utc()
        if log and log.status in {"sent", "unregistered"}:
            continue
        if (
            log
            and log.status == "pending"
            and log.last_attempt_at > attempt_time - timedelta(minutes=10)
        ):
            continue
        if log is None:
            log = NotificationLog(
                user_id=user_id,
                device_id=device.id,
                event_key=event_key,
                kind=kind,
                status="pending",
                attempts=1,
                last_attempt_at=attempt_time,
            )
            db.add(log)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                continue
        else:
            log.status = "pending"
            log.attempts += 1
            log.last_attempt_at = attempt_time
            await db.commit()
        token = decrypt_field(device.token_encrypted)
        result = await provider.send(token, title, body, data or {})
        log.status = result
        log.last_attempt_at = now_utc()
        if result == "sent":
            log.sent_at = now_utc()
            sent += 1
        elif result == "unregistered":
            device.is_valid = False
            device.invalidated_at = now_utc()
        await db.commit()
    return sent
