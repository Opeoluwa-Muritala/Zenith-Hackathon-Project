"""cashlens FastAPI entry point."""

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.router import router as ai_router
from app.ai.client import GroqClient
from app.ai.client_factory import client_for
from app.core.clock import now_utc
from app.core.config import PRODUCT_NAME, get_settings
from app.core.db import SessionLocal, get_db
from app.core.security import access_token, current_user, hash_secret, new_refresh
from app.insights.runner import run_for_user
from app.ledger.recurring import rebuild_account
from app.ledger.service import active_accounts, ingest, ledger_view
from app.models import (
    Account,
    AccountType,
    Consent,
    ConsentAudit,
    Direction,
    InsightRecord,
    Institution,
    ProviderLink,
    RecurringSeries,
    RefreshToken,
    Transaction,
    User,
    WebhookEvent,
)
from app.providers.base import ProviderNotReady, ProviderUnavailable
from app.providers.mock import MockAggregatorProvider
from app.providers.mono import MonoProvider
from app.providers.statement import ProviderError, StatementUploadProvider

settings = get_settings()
settings.validate_runtime()
logger = logging.getLogger("cashlens")
API_VERSION = "1.0.0"
API_DESCRIPTION = """The cashlens API consolidates financial data from user-consented accounts and
returns rule-based summaries and insights. BVN is used only for mocked identity verification;
transaction data comes from the configured aggregator or CSV statements. Money amounts are
integer kobo and timestamps use UTC ISO 8601.

Journey: request and verify an OTP, verify identity, grant consent, link an account, sync
transactions, then read summaries and insights. Protected endpoints use a Bearer access token
obtained from `POST /auth/otp/verify`; refresh tokens are single-use. List endpoints use bounded
`limit`/`offset` pagination where available. Errors use FastAPI's current `detail` response;
validation errors may have a different shape. OTP and account refresh endpoints are rate limited.
Wealth insights are educational information, not financial advice.
"""
OPENAPI_TAGS = [
    {"name": "Auth", "description": "Request an OTP, obtain or rotate tokens, and end a session."},
    {"name": "Identity", "description": "Verify identity; BVN is not a transaction-data source."},
    {"name": "Consents", "description": "Grant, list and revoke scoped data-access consent."},
    {
        "name": "Accounts and linking",
        "description": (
            "Link demo or Mono accounts. Mono flow: initiate, authorise at hosted link, "
            "receive webhook, poll status; SDK code exchange is optional."
        ),
    },
    {
        "name": "Sync and statements",
        "description": "Refresh consented provider data or import a CSV statement.",
    },
    {
        "name": "Transactions",
        "description": "Read filtered transactions; monetary amounts are integer kobo.",
    },
    {"name": "Summary", "description": "Read account totals and spending aggregates."},
    {"name": "Recurring", "description": "Read recurring bills and subscriptions."},
    {"name": "Insights", "description": "Read, run and dismiss deterministic detector results."},
    {"name": "Forecast", "description": "Read the safe-to-spend calculation."},
    {
        "name": "AI",
        "description": "Opt-in wording and aggregate-only chat; model failure falls back safely.",
    },
    {
        "name": "Webhooks",
        "description": "Provider callbacks authenticated by shared-secret header, not JWT.",
    },
    {"name": "Health", "description": "Check service availability."},
]
app = FastAPI(
    title=PRODUCT_NAME,
    version=API_VERSION,
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Project maintainers"},
    license_info={"name": "Unspecified"},
    servers=[{"url": "http://localhost:8000", "description": "Local development"}],
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "none",
    },
)
app.include_router(ai_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
_otp_attempts: dict[str, list[float]] = defaultdict(list)


@app.on_event("startup")
async def check_ai_tool_capability():
    """Check Groq's model catalogue without blocking non-AI startup."""
    app.state.ai_chat_available = True
    if settings.ai_enabled_global and settings.ai_provider == "groq":
        client = client_for()
        try:
            app.state.ai_chat_available = bool(
                isinstance(client, GroqClient)
                and await client.supports_tools(settings.ai_chat_model)
            )
        except Exception as exc:
            app.state.ai_chat_available = False
            logger.warning(
                "ai_chat_capability_check_failed", extra={"error_type": type(exc).__name__}
            )
        if not app.state.ai_chat_available:
            logger.warning("ai_chat_model_lacks_tool_support")


@app.on_event("shutdown")
async def close_ai_http_client():
    """Close a configured shared AI HTTP client during application shutdown."""
    client = client_for()
    if isinstance(client, GroqClient):
        await client.close()


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


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=200)


class LinkIn(BaseModel):
    consent_id: UUID
    institution_code: str = Field(min_length=2, max_length=20)


class ExchangeIn(BaseModel):
    consent_id: UUID
    code: str = Field(min_length=1, max_length=300)


class InitiateIn(BaseModel):
    consent_id: UUID
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


async def owned_consent(db: AsyncSession, user_id: UUID, consent_id: UUID) -> Consent:
    row = (
        await db.execute(
            select(Consent).where(
                Consent.id == consent_id,
                Consent.user_id == user_id,
                Consent.revoked_at.is_(None),
                Consent.expires_at > now_utc(),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Active consent not found")
    return row


def provider():
    if settings.aggregator_provider == "mono":
        return MonoProvider(settings.mono_secret_key, settings.mono_base_url)
    return MockAggregatorProvider()


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


@app.get("/dev/mono-test", include_in_schema=False)
async def mono_test_page(request: Request):
    """Serve the sandbox helper only to loopback clients outside production."""
    client_host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False
    local_host = request.url.hostname in {"localhost", "127.0.0.1", "::1"}
    if settings.environment == "production" or not local_host or not is_loopback:
        raise HTTPException(404, "Not found")
    return FileResponse(
        Path(__file__).parent / "dev" / "mono_test.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; connect-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            ),
        },
    )


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


@app.post("/auth/refresh")
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    """Rotate a refresh token once; replay revokes its entire family."""
    digest = hash_secret(body.refresh_token)
    row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == digest).with_for_update()
        )
    ).scalar_one_or_none()
    now = now_utc()
    if row is None:
        raise HTTPException(401, "Invalid refresh token")
    if row.used_at is not None:
        if row.family_id is None:
            row.revoked_at = now
            await db.commit()
            raise HTTPException(401, "Invalid refresh token")
        family = (
            await db.execute(select(RefreshToken).where(RefreshToken.family_id == row.family_id))
        ).scalars()
        for token in family:
            token.revoked_at = now
        await db.commit()
        raise HTTPException(401, "Invalid refresh token")
    if row.revoked_at or row.expires_at <= now:
        raise HTTPException(401, "Invalid refresh token")
    if row.family_id is None:
        row.family_id = uuid4()
    row.used_at = now
    raw, new_digest = new_refresh()
    db.add(
        RefreshToken(
            user_id=row.user_id,
            family_id=row.family_id,
            token_hash=new_digest,
            expires_at=now + timedelta(days=settings.refresh_days),
            used_at=None,
            revoked_at=None,
        )
    )
    await db.commit()
    return {"access_token": access_token(row.user_id), "refresh_token": raw, "token_type": "bearer"}


@app.post("/auth/logout", status_code=204)
async def logout(
    body: RefreshIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    digest = hash_secret(body.refresh_token)
    row = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == digest, RefreshToken.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row:
        family = (
            await db.execute(select(RefreshToken).where(RefreshToken.family_id == row.family_id))
        ).scalars()
        for token in family:
            token.revoked_at = now_utc()
        await db.commit()


@app.post("/identity/bvn/verify")
async def verify_bvn(
    body: BvnIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    user.bvn_hash = hash_secret(body.bvn, settings.bvn_pepper)
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
    consent_id: UUID,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
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
        links = (
            (
                await db.execute(
                    select(ProviderLink).where(
                        ProviderLink.consent_id == consent.id, ProviderLink.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for link in links:
            link.status = "unlinked"
            if link.provider == "mono" and link.provider_account_id:
                background.add_task(unlink_mono, link.provider_account_id)
        await db.execute(delete(InsightRecord).where(InsightRecord.user_id == user.id))
        await db.commit()


async def unlink_mono(provider_account_id: str):
    """Attempt remote unlink after local revocation; failures do not restore access."""
    try:
        await MonoProvider(settings.mono_secret_key, settings.mono_base_url).unlink(
            provider_account_id
        )
    except Exception:
        logger.warning("Remote provider unlink requires retry")


@app.post("/accounts/link", status_code=201)
async def link_mock(
    body: LinkIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if settings.aggregator_provider != "mock":
        raise HTTPException(409, "Mock account linking is disabled")
    consent = await owned_consent(db, user.id, body.consent_id)
    if consent.institution != body.institution_code:
        raise HTTPException(422, "Institution does not match consent")
    existing = (
        await db.execute(
            select(Account).where(Account.consent_id == consent.id, Account.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing:
        return {"id": existing.id, "status": "connected"}
    institution = (
        await db.execute(select(Institution).where(Institution.code == body.institution_code))
    ).scalar_one_or_none()
    if institution is None:
        institution = Institution(
            name=f"Demo {body.institution_code}",
            code=body.institution_code,
            logo_url=None,
            savings_rate_bps=100,
        )
        db.add(institution)
        await db.flush()
    account = Account(
        user_id=user.id,
        institution_id=institution.id,
        consent_id=consent.id,
        account_number_masked="******0001",
        type=AccountType.current,
        currency="NGN",
        current_balance_minor=5_000_000,
        last_synced_at=None,
    )
    db.add(account)
    await db.flush()
    db.add(
        ProviderLink(
            user_id=user.id,
            consent_id=consent.id,
            provider="mock",
            provider_account_id=(
                "salaried"
                if user.phone.endswith("001")
                else "freelancer"
                if user.phone.endswith("002")
                else "student"
                if user.phone.endswith("003")
                else "demo"
            )
            + ":"
            + str(account.id),
            status="connected",
            data_status="AVAILABLE",
            created_at=now_utc(),
            last_webhook_at=None,
        )
    )
    await db.commit()
    return {"id": account.id, "status": "connected"}


@app.post("/accounts/link/initiate", status_code=201)
async def initiate_link(
    body: InitiateIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if settings.aggregator_provider != "mono":
        raise HTTPException(409, "Mono linking is disabled")
    await owned_consent(db, user.id, body.consent_id)
    link = ProviderLink(
        user_id=user.id,
        consent_id=body.consent_id,
        provider="mono",
        provider_account_id=None,
        status="pending",
        data_status="PROCESSING",
        created_at=now_utc(),
        last_webhook_at=None,
    )
    db.add(link)
    await db.flush()
    url = await provider().initiate(
        body.name, str(body.email), str(link.id), settings.mono_redirect_url
    )
    await db.commit()
    return {"ref": link.id, "url": url, "status": "pending"}


@app.get("/accounts/link/status")
async def link_status(
    ref: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    link = (
        await db.execute(
            select(ProviderLink).where(ProviderLink.id == ref, ProviderLink.user_id == user.id)
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(404, "Link not found")
    return {"ref": link.id, "status": link.status, "data_status": link.data_status}


@app.post("/accounts/link/exchange")
async def exchange_link(
    body: ExchangeIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if settings.aggregator_provider != "mono":
        raise HTTPException(409, "Mono linking is disabled")
    await owned_consent(db, user.id, body.consent_id)
    provider_id = await provider().exchange(body.code)
    if not provider_id:
        raise HTTPException(502, "Provider did not return an account")
    link = ProviderLink(
        user_id=user.id,
        consent_id=body.consent_id,
        provider="mono",
        provider_account_id=provider_id,
        status="connected",
        data_status="PROCESSING",
        created_at=now_utc(),
        last_webhook_at=None,
    )
    db.add(link)
    await db.commit()
    return {"ref": link.id, "status": "connected"}


async def process_mono_event(event: dict):
    """Apply an authenticated Mono event, then sync if account data is ready."""
    name = event.get("event")
    data = event.get("data") or {}
    meta = data.get("meta") or {}
    account_data = data.get("account") or {}
    ref = meta.get("ref")
    account_id = (
        data.get("id")
        if name == "mono.events.account_connected"
        else (account_data.get("_id") or account_data.get("id"))
    )
    async with SessionLocal() as db:
        link = None
        if ref:
            try:
                link = await db.get(ProviderLink, UUID(str(ref)))
            except ValueError:
                return
        if link is None and account_id:
            link = (
                await db.execute(
                    select(ProviderLink).where(
                        ProviderLink.provider == "mono",
                        ProviderLink.provider_account_id == account_id,
                    )
                )
            ).scalar_one_or_none()
        if link is None:
            return
        consent = await db.get(Consent, link.consent_id)
        if consent is None or consent.revoked_at or consent.expires_at <= now_utc():
            return
        link.last_webhook_at = now_utc()
        if name == "mono.events.account_unlinked":
            link.status = "unlinked"
            consent.revoked_at = now_utc()
            db.add(
                ConsentAudit(
                    consent_id=consent.id,
                    event="revoked_by_provider",
                    actor="mono",
                    at=consent.revoked_at,
                )
            )
            await db.execute(delete(InsightRecord).where(InsightRecord.user_id == link.user_id))
            await db.commit()
            return
        if name not in {"mono.events.account_connected", "mono.events.account_updated"}:
            return
        if account_id:
            link.provider_account_id = str(account_id)
            link.status = "connected"
        link.data_status = meta.get("data_status")
        if link.data_status not in {"AVAILABLE", "PARTIAL"} or not link.provider_account_id:
            await db.commit()
            return
        details = await provider().details(link.provider_account_id)
        details_data = details.get("data") or {}
        info = details_data.get("account") or {}
        bank = info.get("institution") or {}
        code = str(bank.get("bank_code") or bank.get("bankCode") or consent.institution)[:20]
        institution = (
            await db.execute(select(Institution).where(Institution.code == code))
        ).scalar_one_or_none()
        if institution is None:
            institution = Institution(
                name=str(bank.get("name") or consent.institution)[:80],
                code=code,
                logo_url=None,
                savings_rate_bps=0,
            )
            db.add(institution)
            await db.flush()
        account = (
            await db.execute(
                select(Account).where(
                    Account.user_id == link.user_id, Account.consent_id == consent.id
                )
            )
        ).scalar_one_or_none()
        if account is None:
            account = Account(
                user_id=link.user_id,
                consent_id=consent.id,
                institution_id=institution.id,
                account_number_masked="******"
                + str(info.get("account_number") or info.get("accountNumber") or "0000")[-4:],
                type=AccountType.savings
                if "sav" in str(info.get("type", "")).lower()
                else AccountType.current,
                currency="NGN",
                current_balance_minor=int(info.get("balance") or 0),
                last_synced_at=None,
            )
            db.add(account)
            await db.flush()
        else:
            account.current_balance_minor = int(
                info.get("balance") or account.current_balance_minor
            )
        await db.commit()
        try:
            await sync_owned_account(db, account, link, now_utc())
            await db.commit()
        except (ProviderNotReady, ProviderUnavailable, HTTPException):
            await db.rollback()


@app.post("/webhooks/mono")
async def mono_webhook(
    request: Request,
    background: BackgroundTasks,
    mono_webhook_secret: str | None = Header(default=None),
):
    if (
        not settings.webhook_secure_key
        or not mono_webhook_secret
        or not hmac.compare_digest(mono_webhook_secret, settings.webhook_secure_key)
    ):
        raise HTTPException(401, "Unauthorised")
    raw = await request.body()
    if len(raw) > 64_000:
        raise HTTPException(413, "Webhook too large")
    try:
        event = json.loads(raw)
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, "Invalid webhook") from exc
    event_key = hashlib.sha256(str(event.get("event_id") or raw.hex()).encode()).hexdigest()
    async with SessionLocal() as db:
        if (
            await db.execute(select(WebhookEvent.id).where(WebhookEvent.event_key == event_key))
        ).scalar_one_or_none():
            return {"received": True}
        db.add(
            WebhookEvent(
                event_key=event_key, event_name=event["event"][:100], received_at=now_utc()
            )
        )
        await db.commit()
    if event["event"] in {
        "mono.events.account_connected",
        "mono.events.account_updated",
        "mono.events.account_unlinked",
    }:
        background.add_task(process_mono_event, event)
    return {"received": True}


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


async def sync_owned_account(
    db: AsyncSession, account: Account, link: ProviderLink, now: datetime
) -> int:
    """Fetch a bounded provider window and rebuild derived user data."""
    await owned_consent(db, account.user_id, account.consent_id)
    if link.status != "connected":
        raise HTTPException(409, "Account is not connected")
    try:
        rows = await provider().transactions(
            link.provider_account_id, now - timedelta(days=190), now
        )
    except ProviderNotReady as exc:
        raise HTTPException(409, "Provider data is not ready") from exc
    except ProviderUnavailable as exc:
        raise HTTPException(503, "Provider temporarily unavailable") from exc
    if len(rows) > 10_000:
        raise HTTPException(502, "Provider returned too many transactions")
    count = await ingest(db, account, rows)
    await db.flush()
    await rebuild_account(db, account.id, account.user_id, now)
    await db.flush()
    await db.execute(
        delete(InsightRecord).where(
            InsightRecord.user_id == account.user_id, InsightRecord.dismissed_at.is_(None)
        )
    )
    await run_for_user(db, account.user_id, now)
    return count


@app.post("/sync")
async def sync(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    now = now_utc()
    account_ids = active_accounts(user.id, now)
    pairs = (
        await db.execute(
            select(Account, ProviderLink)
            .join(ProviderLink, ProviderLink.consent_id == Account.consent_id)
            .where(
                Account.id.in_(account_ids),
                ProviderLink.user_id == user.id,
                ProviderLink.status == "connected",
            )
        )
    ).all()
    count = 0
    for account, link in pairs:
        count += await sync_owned_account(db, account, link, now)
    await db.commit()
    return {"accounts_synced": len(pairs), "transactions_imported": count}


@app.post("/accounts/{account_id}/refresh")
async def refresh_account(
    account_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    account = (
        await db.execute(
            select(Account).where(
                Account.id == account_id,
                Account.user_id == user.id,
                Account.id.in_(active_accounts(user.id, now_utc())),
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Account not found")
    link = (
        await db.execute(
            select(ProviderLink).where(
                ProviderLink.consent_id == account.consent_id,
                ProviderLink.user_id == user.id,
                ProviderLink.status == "connected",
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(404, "Link not found")
    if account.last_synced_at and now_utc() - account.last_synced_at < timedelta(hours=1):
        raise HTTPException(429, "Refresh available once per hour")
    if link.provider == "mono":
        await provider().details(link.provider_account_id, realtime=True)
    count = await sync_owned_account(db, account, link, now_utc())
    await db.commit()
    return {"transactions_imported": count}


@app.get("/summary/overview")
async def summary(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Return a rolling 30-day summary over consented accounts."""
    active = (
        select(Account.id)
        .join(Consent)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    tx = (
        (
            await db.execute(
                select(Transaction).where(
                    Transaction.account_id.in_(active),
                    Transaction.posted_at >= now_utc() - timedelta(days=30),
                )
            )
        )
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


@app.get("/summary/monthly")
async def monthly_summary(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    view, _ = await ledger_view(db, user.id, now_utc())
    months: dict[str, dict[str, int]] = {}
    for tx in view.transactions:
        key = tx.posted_at.strftime("%Y-%m")
        slot = months.setdefault(key, {"income_minor": 0, "spend_minor": 0})
        slot["income_minor" if tx.direction == "credit" else "spend_minor"] += tx.amount
    return [
        {"month": key, **value, "net_minor": value["income_minor"] - value["spend_minor"]}
        for key, value in sorted(months.items())[-6:]
    ]


@app.get("/summary/categories")
async def category_summary(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    view, _ = await ledger_view(db, user.id, now_utc())
    categories: dict[str, int] = {}
    for tx in view.transactions:
        if tx.direction == "debit" and tx.posted_at >= now_utc() - timedelta(days=30):
            categories[tx.category] = categories.get(tx.category, 0) + tx.amount
    total = sum(categories.values())
    return [
        {
            "category": key,
            "amount_minor": value,
            "share_bps": value * 10_000 // total if total else 0,
        }
        for key, value in sorted(categories.items())
    ]


@app.get("/transactions")
async def transactions(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
    account_id: UUID | None = None,
    merchant_id: UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise HTTPException(422, "Invalid pagination")
    if from_date and to_date and (to_date < from_date or to_date - from_date > timedelta(days=365)):
        raise HTTPException(422, "Invalid date range")
    active = (
        select(Account.id)
        .join(Consent)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    q = select(Transaction).where(Transaction.account_id.in_(active))
    q = q.where(Transaction.category == category) if category else q
    q = q.where(Transaction.account_id == account_id) if account_id else q
    q = q.where(Transaction.merchant_id == merchant_id) if merchant_id else q
    q = q.where(Transaction.posted_at >= from_date) if from_date else q
    q = q.where(Transaction.posted_at <= to_date) if to_date else q
    rows = (
        await db.execute(q.order_by(Transaction.posted_at.desc()).offset(offset).limit(limit))
    ).scalars()
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
async def upload_statement(
    account_id: UUID,
    file: Annotated[UploadFile, File()],
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/csv"}:
        raise HTTPException(415, "CSV required")
    data = await file.read(2_000_001)
    try:
        rows = StatementUploadProvider().parse(data)
    except (ProviderError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    account = (
        await db.execute(
            select(Account).where(
                Account.id == account_id,
                Account.user_id == user.id,
                Account.id.in_(active_accounts(user.id, now_utc())),
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Account not found")
    imported = await ingest(db, account, rows)
    await db.flush()
    await rebuild_account(db, account.id, user.id, now_utc())
    await db.flush()
    await db.execute(
        delete(InsightRecord).where(
            InsightRecord.user_id == user.id, InsightRecord.dismissed_at.is_(None)
        )
    )
    await run_for_user(db, user.id, now_utc())
    await db.commit()
    return {"accepted": len(rows), "imported": imported}


@app.get("/recurring")
async def recurring(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(RecurringSeries).where(
                RecurringSeries.user_id == user.id,
                RecurringSeries.account_id.in_(active_accounts(user.id, now_utc())),
            )
        )
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
        "wording_source": x.wording_source,
        "template_title": x.template_title,
        "template_body": x.template_body,
        "payload": x.payload_json,
        "created_at": x.created_at,
        "footer": "Educational information, not financial advice."
        if x.module == "wealth"
        else None,
    }


async def insight_is_authorised(db: AsyncSession, user_id: UUID, row: InsightRecord) -> bool:
    """Hide stored insights once any source account loses active consent."""
    view, _ = await ledger_view(db, user_id, now_utc())
    source_ids = row.payload_json.get("source_account_ids")
    if not isinstance(source_ids, list) or not source_ids:
        return False
    return set(source_ids) <= {b.account_id for b in view.balances}


@app.get("/insights")
async def insights(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    module: str | None = None,
):
    view, _ = await ledger_view(db, user.id, now_utc())
    active_ids = {balance.account_id for balance in view.balances}
    q = select(InsightRecord).where(
        InsightRecord.user_id == user.id, InsightRecord.dismissed_at.is_(None)
    )
    q = q.where(InsightRecord.module == module) if module else q
    return [
        insight_out(x)
        for x in (await db.execute(q)).scalars()
        if x.payload_json.get("source_account_ids")
        and set(x.payload_json["source_account_ids"]) <= active_ids
    ]


@app.post("/insights/run")
async def run_insights(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    created = await run_for_user(db, user.id, now_utc())
    await db.commit()
    return {"created": created}


@app.get("/forecast/safe-to-spend")
async def safe_to_spend_forecast(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    from app.insights.detectors.safe_to_spend import detect

    view, user_settings = await ledger_view(db, user.id, now_utc())
    found = detect(view, user_settings, now_utc())
    return found[0].payload if found else {"status": "insufficient_data"}


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
    if not row or not await insight_is_authorised(db, user.id, row):
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


def _document_operation(path: str, method: str, operation: dict) -> None:
    """Add stable Swagger metadata without changing route behaviour."""
    groups = {
        "/auth/": "Auth",
        "/identity/": "Identity",
        "/consents": "Consents",
        "/accounts": "Accounts and linking",
        "/sync": "Sync and statements",
        "/statements/": "Sync and statements",
        "/transactions": "Transactions",
        "/summary/": "Summary",
        "/recurring": "Recurring",
        "/insights": "Insights",
        "/forecast/": "Forecast",
        "/settings/ai": "AI",
        "/ai/": "AI",
        "/webhooks/": "Webhooks",
        "/health": "Health",
    }
    tag = next(
        (name for prefix, name in groups.items() if path.startswith(prefix)), "Accounts and linking"
    )
    operation["tags"] = [tag]
    method = method.upper()
    verb = {"GET": "Read", "POST": "Submit", "PATCH": "Update", "DELETE": "Delete"}.get(
        method, "Manage"
    )
    readable = path.strip("/").replace("/", " ").replace("{", "by ").replace("}", "") or "health"
    operation.setdefault("summary", f"{verb} {readable}"[:59])
    operation.setdefault(
        "description",
        (
            f"{verb} this resource in the cashlens user journey. Protected operations "
            "require the signed-in user's Bearer access token and scope data to that user. "
            "Amounts are integer kobo; timestamps are UTC ISO 8601. State-changing operations "
            "may update consent, ledger, or derived insight data as described by the route."
        ),
    )
    operation_id = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        f"{method.lower()}_{path.strip('/')}".replace("{", "by_").replace("}", ""),
    ).strip("_")
    operation["operationId"] = operation_id


def custom_openapi():
    """Generate ordered, stable OpenAPI metadata for Swagger UI and ReDoc."""
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema["servers"] = app.servers
    seen: set[str] = set()
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            _document_operation(path, method, operation)
            if operation.get("security"):
                operation.setdefault("responses", {}).setdefault(
                    "401",
                    {
                        "description": "Authentication is missing or invalid.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"detail": {"type": "string"}},
                                    "required": ["detail"],
                                }
                            }
                        },
                    },
                )
            operation_id = operation["operationId"]
            if operation_id in seen:
                operation["operationId"] = f"{operation_id}_{len(seen)}"
            seen.add(operation["operationId"])
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
