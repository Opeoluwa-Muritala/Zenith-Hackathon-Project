"""Owner, share-link and bookkeeper read-only reporting API."""

import secrets
from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import current_user, hash_secret
from app.ledger.normalise import category_label
from app.ledger.service import active_accounts
from app.models import (
    BookkeeperInvite,
    ReportShareLink,
    Transaction,
    User,
)
from app.reports.export import render_csv, render_pdf
from app.reports.service import MonthlyReport, build_monthly_report, parse_month

router = APIRouter(tags=["Reports"])


class ShareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


def _month(value: str):
    try:
        return parse_month(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _download(report: MonthlyReport, export_format: Literal["pdf", "csv"]) -> Response:
    if export_format == "pdf":
        content, media_type = render_pdf(report), "application/pdf"
    else:
        content, media_type = render_csv(report), "text/csv; charset=utf-8"
    filename = f"fetch-report-{report.month}.{export_format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _bookkeeper_access(
    db: AsyncSession, owner_id: UUID, bookkeeper_id: UUID
) -> BookkeeperInvite:
    row = await db.scalar(
        select(BookkeeperInvite).where(
            BookkeeperInvite.owner_user_id == owner_id,
            BookkeeperInvite.accepted_by_user_id == bookkeeper_id,
            BookkeeperInvite.status == "accepted",
            BookkeeperInvite.revoked_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(404, "Client not found")
    return row


@router.get("/reports/monthly/{month}", response_model=MonthlyReport)
async def monthly_report(
    month: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonthlyReport:
    return await build_monthly_report(db, user.id, _month(month), now_utc())


@router.get("/reports/monthly/{month}/export")
async def export_monthly_report(
    month: str,
    format: Literal["pdf", "csv"],
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    report = await build_monthly_report(db, user.id, _month(month), now_utc())
    return _download(report, format)


@router.post("/reports/monthly/{month}/share-links", status_code=201)
async def create_report_share_link(
    month: str,
    body: ShareInput,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    report_month = _month(month)
    raw = secrets.token_urlsafe(32)
    row = ReportShareLink(
        user_id=user.id,
        month=report_month,
        token_hash=hash_secret(raw, "report-share"),
        created_at=now_utc(),
        expires_at=now_utc() + timedelta(days=body.expires_in_days),
    )
    db.add(row)
    await db.commit()
    url = f"{get_settings().public_base_url.rstrip('/')}/shared/reports/{raw}"
    return {"id": row.id, "url": url, "expires_at": row.expires_at}


@router.get("/report-share-links")
async def list_report_share_links(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    rows = (
        await db.scalars(
            select(ReportShareLink)
            .where(ReportShareLink.user_id == user.id)
            .order_by(ReportShareLink.created_at.desc())
        )
    ).all()
    return [
        {
            "id": row.id,
            "month": row.month.strftime("%Y-%m"),
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
        }
        for row in rows
    ]


@router.delete("/report-share-links/{link_id}", status_code=204)
async def revoke_report_share_link(
    link_id: UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.scalar(
        select(ReportShareLink)
        .where(ReportShareLink.id == link_id, ReportShareLink.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Share link not found")
    row.revoked_at = row.revoked_at or now_utc()
    await db.commit()


async def _shared_link(db: AsyncSession, token: str) -> ReportShareLink:
    if not 32 <= len(token) <= 200:
        raise HTTPException(404, "Shared report not found")
    row = await db.scalar(
        select(ReportShareLink).where(
            ReportShareLink.token_hash == hash_secret(token, "report-share"),
            ReportShareLink.revoked_at.is_(None),
            ReportShareLink.expires_at > now_utc(),
        )
    )
    if row is None:
        raise HTTPException(404, "Shared report not found")
    return row


@router.get("/shared/reports/{token}", response_model=MonthlyReport)
async def shared_report(token: str, db: Annotated[AsyncSession, Depends(get_db)]) -> MonthlyReport:
    row = await _shared_link(db, token)
    return await build_monthly_report(db, row.user_id, row.month, now_utc())


@router.get("/shared/reports/{token}/export")
async def export_shared_report(
    token: str,
    format: Literal["pdf", "csv"],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    row = await _shared_link(db, token)
    report = await build_monthly_report(db, row.user_id, row.month, now_utc())
    return _download(report, format)


@router.post("/bookkeeper-invites", status_code=201)
async def invite_bookkeeper(
    body: InviteInput,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    email = body.email.lower()
    if user.email and user.email.lower() == email:
        raise HTTPException(422, "Invite a different user")
    row = await db.scalar(
        select(BookkeeperInvite).where(BookkeeperInvite.owner_user_id == user.id).with_for_update()
    )
    if row and row.status in {"pending", "accepted"} and row.revoked_at is None:
        raise HTTPException(409, "One bookkeeper is already invited")
    raw = secrets.token_urlsafe(32)
    values = {
        "email": email,
        "token_hash": hash_secret(raw, "bookkeeper-invite"),
        "status": "pending",
        "accepted_by_user_id": None,
        "created_at": now_utc(),
        "expires_at": now_utc() + timedelta(days=7),
        "revoked_at": None,
    }
    if row is None:
        row = BookkeeperInvite(owner_user_id=user.id, **values)
        db.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "One bookkeeper is already invited") from exc
    url = f"{get_settings().public_base_url.rstrip('/')}/bookkeeper-invites/{raw}/accept"
    return {"id": row.id, "email": row.email, "status": row.status, "invite_url": url}


@router.get("/bookkeeper-invites")
async def get_bookkeeper_invite(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict | None:
    row = await db.scalar(select(BookkeeperInvite).where(BookkeeperInvite.owner_user_id == user.id))
    if row is None:
        return None
    return {
        "id": row.id,
        "email": row.email,
        "status": row.status,
        "expires_at": row.expires_at,
        "revoked_at": row.revoked_at,
    }


@router.delete("/bookkeeper-invites/{invite_id}", status_code=204)
async def revoke_bookkeeper_invite(
    invite_id: UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.scalar(
        select(BookkeeperInvite)
        .where(BookkeeperInvite.id == invite_id, BookkeeperInvite.owner_user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Invite not found")
    row.status, row.revoked_at = "revoked", now_utc()
    await db.commit()


@router.post("/bookkeeper-invites/{token}/accept")
async def accept_bookkeeper_invite(
    token: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if not 32 <= len(token) <= 200:
        raise HTTPException(404, "Invite not found")
    if not user.email:
        raise HTTPException(403, "Invite email does not match")
    row = await db.scalar(
        select(BookkeeperInvite)
        .where(
            BookkeeperInvite.token_hash == hash_secret(token, "bookkeeper-invite"),
            BookkeeperInvite.status == "pending",
            BookkeeperInvite.revoked_at.is_(None),
            BookkeeperInvite.expires_at > now_utc(),
        )
        .with_for_update()
    )
    if row is None or row.email.lower() != user.email.lower():
        raise HTTPException(404, "Invite not found")
    row.status, row.accepted_by_user_id = "accepted", user.id
    await db.commit()
    return {"owner_user_id": row.owner_user_id, "status": row.status}


@router.get("/bookkeeper/clients/{owner_id}/reports/monthly/{month}", response_model=MonthlyReport)
async def bookkeeper_report(
    owner_id: UUID,
    month: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonthlyReport:
    await _bookkeeper_access(db, owner_id, user.id)
    return await build_monthly_report(db, owner_id, _month(month), now_utc())


@router.get("/bookkeeper/clients/{owner_id}/transactions")
async def bookkeeper_ledger(
    owner_id: UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> list[dict]:
    await _bookkeeper_access(db, owner_id, user.id)
    rows = (
        await db.scalars(
            select(Transaction)
            .where(Transaction.account_id.in_(active_accounts(owner_id, now_utc())))
            .order_by(Transaction.posted_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": row.id,
            "posted_at": row.posted_at,
            "amount_minor": row.amount_minor,
            "direction": row.direction,
            "merchant": row.decoded_merchant,
            "category": category_label(row.category),
            "confidence_bps": row.parse_confidence_bps,
        }
        for row in rows
    ]
