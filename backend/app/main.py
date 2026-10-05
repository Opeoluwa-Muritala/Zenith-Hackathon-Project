"""cashlens FastAPI entry point."""

import hmac
import time
from collections import defaultdict
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import PRODUCT_NAME, get_settings
from app.core.db import get_db
from app.core.security import access_token, current_user, hash_secret, new_refresh
from app.models import (
    Account,
    Consent,
    ConsentAudit,
    Direction,
    InsightRecord,
    RecurringSeries,
    RefreshToken,
    Transaction,
    User,
)
from app.providers.statement import ProviderError, StatementUploadProvider

settings = get_settings()
app = FastAPI(title=PRODUCT_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
_otp_attempts: dict[str, list[float]] = defaultdict(list)


class PhoneIn(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class OtpIn(PhoneIn):
    otp: str = Field(min_length=6, max_length=6)


class BvnIn(BaseModel):
    bvn: str = Field(pattern=r"^\d{11}$")


class ConsentIn(BaseModel):
    institution: str = Field(min_length=2, max_length=80)
    scope: str = Field(pattern=r"^[a-z,_-]{1,100}$")
    expires_in_days: int = Field(30, ge=1, le=365)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "product": PRODUCT_NAME}


def rate_limit(phone):
    now = time.monotonic()
    _otp_attempts[phone] = [x for x in _otp_attempts[phone] if now - x < 60]
    if len(_otp_attempts[phone]) >= 5:
        raise HTTPException(429, "Try again later")
    _otp_attempts[phone].append(now)


@app.post("/auth/otp/request", status_code=202)
async def request_otp(body: PhoneIn):
    rate_limit(body.phone)
    return {"status": "sent"}


@app.post("/auth/otp/verify")
async def verify_otp(body: OtpIn, db: AsyncSession = Depends(get_db)):
    rate_limit(body.phone)
    if settings.environment == "production" or not hmac.compare_digest(body.otp, settings.dev_otp):
        raise HTTPException(401, "Invalid code")
    user = (await db.execute(select(User).where(User.phone == body.phone))).scalar_one_or_none()
    if not user:
        user = User(
            phone=body.phone, email=None, bvn_hash=None, bvn_last4=None, created_at=now_utc()
        )
        db.add(user)
        await db.flush()
    raw, digest = new_refresh()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=now_utc() + timedelta(days=settings.refresh_days),
            used_at=None,
        )
    )
    await db.commit()
    return {"access_token": access_token(user.id), "refresh_token": raw, "token_type": "bearer"}


@app.post("/identity/bvn/verify")
async def verify_bvn(
    body: BvnIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    salt = settings.jwt_secret[-16:]
    user.bvn_hash = hash_secret(body.bvn, salt)
    user.bvn_last4 = body.bvn[-4:]
    await db.commit()
    return {
        "verified": True,
        "profile": {"name": f"Demo Customer {body.bvn[-2:]}", "bvn_last4": body.bvn[-4:]},
    }


@app.post("/consents", status_code=201)
async def create_consent(
    body: ConsentIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    now = now_utc()
    consent = Consent(
        user_id=user.id,
        institution=body.institution,
        scope=body.scope,
        granted_at=now,
        expires_at=now + timedelta(days=body.expires_in_days),
        revoked_at=None,
    )
    db.add(consent)
    await db.flush()
    db.add(ConsentAudit(consent_id=consent.id, event="granted", actor=str(user.id), at=now))
    await db.commit()
    return {"id": consent.id, "institution": consent.institution, "scope": consent.scope}


@app.get("/consents")
async def consents(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Consent).where(Consent.user_id == user.id))).scalars()
    return [
        {"id": x.id, "institution": x.institution, "scope": x.scope, "revoked_at": x.revoked_at}
        for x in rows
    ]


@app.delete("/consents/{consent_id}", status_code=204)
async def revoke(
    consent_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    consent = (
        await db.execute(
            select(Consent).where(Consent.id == consent_id, Consent.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not consent:
        raise HTTPException(404, "Consent not found")
    if not consent.revoked_at:
        consent.revoked_at = now_utc()
        db.add(
            ConsentAudit(
                consent_id=consent.id, event="revoked", actor=str(user.id), at=consent.revoked_at
            )
        )
        await db.commit()


@app.get("/accounts")
async def accounts(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = (
        select(Account)
        .join(Consent, Account.consent_id == Consent.id)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    rows = (await db.execute(q)).scalars()
    return [
        {
            "id": x.id,
            "type": x.type,
            "currency": x.currency,
            "balance_minor": x.current_balance_minor,
            "account_number_masked": x.account_number_masked,
        }
        for x in rows
    ]


@app.get("/summary/overview")
async def summary(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    active = (
        select(Account.id)
        .join(Consent)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    tx = (
        (await db.execute(select(Transaction).where(Transaction.account_id.in_(active))))
        .scalars()
        .all()
    )
    bal = (
        await db.execute(
            select(func.coalesce(func.sum(Account.current_balance_minor), 0)).where(
                Account.id.in_(active)
            )
        )
    ).scalar_one()
    income = sum(x.amount_minor for x in tx if x.direction == Direction.credit)
    spend = sum(x.amount_minor for x in tx if x.direction == Direction.debit)
    return {
        "income_minor": income,
        "spend_minor": spend,
        "savings_rate_bps": (income - spend) * 10000 // income if income else 0,
        "total_balance_minor": bal,
    }


@app.get("/transactions")
async def transactions(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
):
    active = (
        select(Account.id)
        .join(Consent)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    q = select(Transaction).where(Transaction.account_id.in_(active))
    q = q.where(Transaction.category == category) if category else q
    rows = (await db.execute(q.order_by(Transaction.posted_at.desc()).limit(500))).scalars()
    return [
        {
            "id": x.id,
            "posted_at": x.posted_at,
            "amount_minor": x.amount_minor,
            "direction": x.direction,
            "narration": x.narration_clean,
            "category": x.category,
        }
        for x in rows
    ]


@app.post("/statements/upload")
async def upload_statement(file: Annotated[UploadFile, File()], user: User = Depends(current_user)):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/csv"}:
        raise HTTPException(415, "CSV required")
    data = await file.read(2_000_001)
    try:
        rows = StatementUploadProvider().parse(data)
    except (ProviderError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"accepted": len(rows)}


@app.get("/recurring")
async def recurring(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(RecurringSeries).where(RecurringSeries.user_id == user.id))
    ).scalars()
    return [
        {
            "id": x.id,
            "amount_minor": x.last_amount_minor,
            "next_expected_at": x.next_expected_at,
            "status": x.status,
            "annualised_minor": x.last_amount_minor * 365 // x.cadence_days,
        }
        for x in rows
    ]


def insight_out(x):
    return {
        "id": x.id,
        "module": x.module,
        "kind": x.kind,
        "severity": x.severity,
        "title": x.title,
        "body": x.body,
        "payload": x.payload_json,
        "created_at": x.created_at,
        "footer": "Educational information, not financial advice."
        if x.module == "wealth"
        else None,
    }


@app.get("/insights")
async def insights(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    module: str | None = None,
):
    q = select(InsightRecord).where(
        InsightRecord.user_id == user.id, InsightRecord.dismissed_at.is_(None)
    )
    q = q.where(InsightRecord.module == module) if module else q
    return [insight_out(x) for x in (await db.execute(q)).scalars()]


@app.get("/insights/{insight_id}")
async def insight_detail(
    insight_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = (
        await db.execute(
            select(InsightRecord).where(
                InsightRecord.id == insight_id, InsightRecord.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Insight not found")
    return insight_out(row)


@app.post("/insights/{insight_id}/dismiss", status_code=204)
async def dismiss(
    insight_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = (
        await db.execute(
            select(InsightRecord).where(
                InsightRecord.id == insight_id, InsightRecord.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Insight not found")
    row.dismissed_at = now_utc()
    await db.commit()
