"""Authenticated consent inventory and complete-data-wipe endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import current_user
from app.identity.otp import code_matches, forget_code
from app.ledger.service import as_utc
from app.models import Consent, OtpCode, PendingUnlink, ProviderLink, User
from app.privacy.service import purge_user, queue_provider_link, retry_pending_unlink

router = APIRouter(tags=["Privacy"])


class WipeRequest(BaseModel):
    otp: str = Field(pattern=r"^\d{6}$")


class ActiveConsentResponse(BaseModel):
    consent_id: UUID
    link_id: UUID
    institution: str
    linked_at: datetime
    data_status: str | None
    scope: str
    read_only: bool


class WipeResponse(BaseModel):
    status: str
    deleted: dict[str, int]
    unlink_pending: bool


async def require_fresh_otp(db: AsyncSession, user: User, otp: str) -> None:
    identifier = user.phone or user.email
    if not identifier:
        raise HTTPException(409, "No verified sign-in identifier")
    row = await db.scalar(
        select(OtpCode)
        .where(OtpCode.identifier == identifier)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    now = now_utc()
    expiry = as_utc(row.expires_at) if row is not None else None
    if (
        row is None
        or row.consumed_at is not None
        or expiry is None
        or expiry <= now
        or row.attempts >= get_settings().otp_max_attempts
        or not code_matches(identifier, otp, row.salt, row.code_hash)
    ):
        if row and row.consumed_at is None:
            row.attempts += 1
            if row.attempts >= get_settings().otp_max_attempts:
                row.consumed_at = now
        await db.commit()
        raise HTTPException(401, "Invalid code")
    row.consumed_at = now
    forget_code(identifier)


@router.get("/privacy/consents", response_model=list[ActiveConsentResponse])
async def active_consents(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    rows = (
        await db.execute(
            select(Consent, ProviderLink)
            .join(ProviderLink, ProviderLink.consent_id == Consent.id)
            .where(
                Consent.user_id == user.id,
                Consent.revoked_at.is_(None),
                ProviderLink.status.notin_(("unlinked", "pending_unlink")),
            )
            .order_by(ProviderLink.created_at)
        )
    ).all()
    return [
        {
            "consent_id": consent.id,
            "link_id": link.id,
            "institution": consent.institution,
            "linked_at": link.created_at,
            "data_status": link.data_status,
            "scope": consent.scope,
            "read_only": True,
        }
        for consent, link in rows
    ]


@router.post("/privacy/wipe", response_model=WipeResponse)
async def wipe(
    body: WipeRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await require_fresh_otp(db, user, body.otp)
    links = (await db.scalars(select(ProviderLink).where(ProviderLink.user_id == user.id))).all()
    queued: list[PendingUnlink] = []
    for link in links:
        row = await queue_provider_link(db, link)
        if row is not None:
            queued.append(row)
    await db.commit()  # Make retry targets durable before any remote call or user deletion.

    pending = False
    for row in queued:
        completed = await retry_pending_unlink(db, row)
        if completed:
            await db.delete(row)
        else:
            pending = True
        await db.commit()

    counts = await purge_user(db, user, now_utc())
    await db.commit()
    return {"status": "wiped", "deleted": counts, "unlink_pending": pending}
