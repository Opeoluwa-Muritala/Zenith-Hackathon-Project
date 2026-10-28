"""cashlens FastAPI entry point."""

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import api_models as api
from app.ai.chat.router import router as ai_router
from app.ai.client import GroqClient
from app.ai.client_factory import client_for
from app.api_documentation import DEMO_OPERATIONS, ERROR_MESSAGES
from app.assets.fx import RATE_SCALE, convert_minor, get_usd_ngn_rate
from app.assets.service import asset_value_ngn_minor, next_reminder
from app.core.clock import now_utc
from app.core.config import PRODUCT_NAME, get_settings
from app.core.db import SessionLocal, get_db
from app.core.encryption import decrypt_field, encrypt_field, hash_field
from app.core.rate_limit import get_rate_limiter
from app.core.security import access_token, current_user, hash_secret, new_refresh
from app.identity.audit import record_auth_event
from app.identity.lockout import clear_failures, ensure_not_locked, register_failure
from app.identity.otp import (
    code_digest,
    code_matches,
    forget_code,
    inbox_code,
    new_code,
    new_salt,
    sender,
)
from app.insights.detectors.velocity_warning import projected_month_end_spend
from app.insights.router import router as insights_phase5_router
from app.insights.runner import run_for_user
from app.ledger.account_categories import category_for_institution
from app.ledger.balances import balance_state
from app.ledger.normalise import (
    CATEGORY_ALIASES,
    FETCH_CATEGORIES,
    category_label,
    counterparty_key,
)
from app.ledger.obligations import sync_detected_obligations
from app.ledger.recurring import rebuild_account
from app.ledger.review import router as classification_review_router
from app.ledger.service import active_accounts, as_utc, ingest, ledger_view
from app.ledger.unlink import purge_linked_account, retry_pending_link
from app.models import (
    Account,
    AccountCategory,
    AccountType,
    Budget,
    BvnLookupSession,
    CategoryRule,
    CategorySource,
    ClassificationCorrection,
    Consent,
    ConsentAudit,
    DeviceToken,
    Direction,
    DiscoveredAccount,
    DiscoveredAccountStatus,
    InsightRecord,
    Institution,
    ManualAsset,
    ManualAssetCategory,
    ManualAssetPlatform,
    Merchant,
    NotificationPreference,
    Obligation,
    ObligationPayment,
    OtpCode,
    ProviderLink,
    RecurringSeries,
    RefreshToken,
    SyncStatus,
    Transaction,
    UpdateCadence,
    User,
    UserSettings,
    WebhookEvent,
)
from app.plans.router import router as plans_router
from app.plans.service import require_live_sync
from app.privacy.router import router as privacy_router
from app.providers.base import ProviderNotReady, ProviderUnavailable
from app.providers.call_budget import reserve_refresh_call
from app.providers.mock import MockAggregatorProvider
from app.providers.mono import MonoProvider
from app.providers.mono_lookup import MonoLookupProvider
from app.providers.statement import ProviderError, StatementUploadProvider
from app.reports.router import router as reports_router

settings = get_settings()
settings.validate_runtime()
logger = logging.getLogger("cashlens")
API_VERSION = "1.0.0"
API_DESCRIPTION = """Fetch consolidates user-consented financial data using Mono Connect or a
mock provider. Authentication uses app-issued JWTs after email or phone OTP verification; refresh
tokens rotate on use. Mono BVN Lookup discovers accounts but does not link them or return balances.
Amounts ending in `_minor` are integer minor units (NGN kobo); timestamps are UTC ISO 8601.
Protected routes require a Bearer access token. Errors use FastAPI's `detail` convention.
Some endpoints use process-local throttles; see the API guide for current limitations.
Financial insights are educational information, not financial advice.
"""
OPENAPI_TAGS = [
    {"name": "Auth", "description": "Request an OTP, obtain or rotate tokens, and end a session."},
    {"name": "Onboarding", "description": "Discover accounts through Mono BVN Lookup."},
    {"name": "Identity", "description": "Verify identity; BVN is not a transaction-data source."},
    {"name": "Assets", "description": "Maintain manual asset values and read net position."},
    {"name": "Category rules", "description": "Manage user-chosen counterparty categories."},
    {"name": "Analytics", "description": "Read spending aggregates across linked accounts."},
    {"name": "Budget", "description": "Set a monthly limit and read spending velocity."},
    {"name": "Obligations", "description": "Review detected and manual upcoming repayments."},
    {"name": "Notifications", "description": "Register devices and set notification preferences."},
    {"name": "Consents", "description": "Grant, list and revoke scoped data-access consent."},
    {"name": "Privacy", "description": "Review active links or permanently wipe user data."},
    {"name": "Plans", "description": "Read entitlements and record upgrade intent."},
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
    {"name": "Reports", "description": "Generate, export and selectively share monthly reports."},
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
    summary="Consented personal-finance data API",
    version=API_VERSION,
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Project maintainers"},
    license_info={"name": "Unspecified"},
    servers=[{"url": settings.public_base_url, "description": "Configured API base URL"}],
    docs_url="/docs" if settings.environment != "production" or settings.api_docs_enabled else None,
    redoc_url="/redoc"
    if settings.environment != "production" or settings.api_docs_enabled
    else None,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "none",
    },
)
app.include_router(ai_router)
app.include_router(classification_review_router)
app.include_router(insights_phase5_router)
app.include_router(reports_router)
app.include_router(privacy_router)
app.include_router(plans_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
_refresh_requests: dict[UUID, float] = {}
presenter_auth = HTTPBasic(auto_error=False)


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
    phone: str | None = Field(
        None,
        description="E.164 phone; Nigerian local format is normalised. "
        "Supply phone or email, not both.",
        examples=["+2348000000000"],
    )
    email: EmailStr | None = Field(
        None,
        description="Login email; supply phone or email, not both.",
        examples=["user@example.com"],
    )

    @model_validator(mode="after")
    def normalise_identifier(self):
        if (self.phone is None) == (self.email is None):
            raise ValueError("Provide one phone or email")
        if self.phone:
            value = self.phone.strip()
            if value.startswith("0") and len(value) == 11 and value.isascii() and value.isdigit():
                value = "+234" + value[1:]
            if not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
                raise ValueError("Phone must be in E.164 format")
            self.phone = value
        if self.email:
            self.email = str(self.email).strip().lower()
        return self

    @property
    def identifier(self) -> str:
        return self.phone or str(self.email)


class OtpIn(PhoneIn):
    otp: str = Field(pattern=r"^[0-9]{6}$")


class BvnIn(BaseModel):
    bvn: str = Field(pattern=r"^[0-9]{11}$")


class BvnMethodIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=100)
    method: Literal["email", "phone", "phone_1", "alternate_phone"]
    phone_number: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_alternate_phone(self):
        if self.method == "alternate_phone" and not (
            self.phone_number
            and re.fullmatch(r"(?:\+[1-9][0-9]{7,14}|0[0-9]{10})", self.phone_number)
        ):
            raise ValueError("A valid phone_number is required for alternate_phone")
        return self


class BvnConfirmIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=100)
    otp: str = Field(pattern=r"^[0-9]{4,8}$")


class ConsentIn(BaseModel):
    institution: str = Field(min_length=2, max_length=80, examples=["Demo Bank"])
    scope: str = Field(pattern=r"^[a-z,_-]{1,100}$", examples=["auth"])
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
    name: str = Field(min_length=2, max_length=100, examples=["Fake User"])
    email: EmailStr


class SelectDiscoveredIn(BaseModel):
    ids: list[UUID] = Field(max_length=100)


class LinkDiscoveredIn(BaseModel):
    email: EmailStr


class ManualAssetIn(BaseModel):
    platform: ManualAssetPlatform
    category: ManualAssetCategory
    currency: Literal["NGN", "USD"]
    amount_minor: int = Field(
        ge=0,
        le=2**63 - 1,
        description="Integer minor units; NGN kobo or USD cents.",
        examples=[10000],
    )
    fx_rate: Decimal | None = Field(
        None,
        description="NGN per USD reference rate, required for USD "
        "when no FX provider is configured.",
        examples=["1500"],
    )
    update_cadence: UpdateCadence


CategoryName = Literal[
    "Food & Dining",
    "Bills & Utilities",
    "Transport",
    "Airtime & Data",
    "Shopping & Transfers",
    "Transfers & Family",
    "Uncategorised",
]


class ReclassifyIn(BaseModel):
    category: CategoryName
    apply_to_future: bool = False


class BudgetIn(BaseModel):
    monthly_limit_minor: int = Field(
        gt=0, le=2**63 - 1, description="Monthly budget in NGN kobo.", examples=[20000000]
    )
    effective_from: datetime | None = Field(
        default=None, description="UTC time when this budget starts applying."
    )


class PrivacyPreferenceIn(BaseModel):
    privacy_blur: bool


class ObligationIn(BaseModel):
    lender_name: str = Field(min_length=2, max_length=120)
    kind: Literal["loan", "direct_debit", "subscription"]
    amount_minor: int = Field(
        gt=0,
        le=2**63 - 1,
        description="Integer minor units; NGN kobo in the demo.",
        examples=[1000000],
    )
    cadence_days: int = Field(ge=1, le=366)
    next_due_date: date
    account_id: UUID | None = None


class ObligationUpdateIn(BaseModel):
    lender_name: str | None = Field(default=None, min_length=2, max_length=120)
    amount_minor: int | None = Field(
        default=None, gt=0, le=2**63 - 1, description="Integer minor units; NGN kobo in the demo."
    )
    cadence_days: int | None = Field(default=None, ge=1, le=366)
    next_due_date: date | None = None
    kind: Literal["loan", "direct_debit", "subscription"] | None = None
    account_id: UUID | None = None
    status: Literal["upcoming", "confirmed", "dismissed"] | None = None


class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=400)
    platform: Literal["android", "ios"]


class NotificationPreferencesIn(BaseModel):
    overspending_alerts: bool = True
    loan_repayment_reminders: bool = True
    investment_update_prompts: bool = True


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


def lookup_provider():
    return MonoLookupProvider(settings.mono_lookup_secret_key, settings.mono_base_url)


_institution_coverage: tuple[float, list[dict]] | None = None


async def resolve_institution(row: DiscoveredAccount) -> dict | None:
    """Map exact bank/NIP codes only; ambiguous coverage remains unmapped."""
    global _institution_coverage
    if _institution_coverage is None or time.monotonic() > _institution_coverage[0]:
        coverage = await provider().institutions()
        _institution_coverage = (time.monotonic() + 3600, coverage)
    matches = [
        item
        for item in _institution_coverage[1]
        if (item.get("bank_code") and str(item["bank_code"]) == row.bank_code)
        or (row.nip_code and str(item.get("nip_code", "")) == row.nip_code)
    ]
    if len(matches) != 1:
        return None
    item = matches[0]
    methods = [m.get("type") for m in item.get("auth_methods", []) if m.get("type")]
    identifier = item.get("_id") or item.get("id")
    if not identifier or len(methods) != 1:
        return None
    return {"id": str(identifier), "auth_method": methods[0]}


def lookup_session_or_410(row: BvnLookupSession | None):
    if row is None or as_utc(row.expires_at) <= now_utc():
        raise HTTPException(410, "BVN lookup session expired; restart the lookup")
    return row


async def mono_call(call):
    """Never forward provider response bodies or credentials to clients."""
    try:
        return await call()
    except ProviderUnavailable:
        raise HTTPException(503, "Mono temporarily unavailable; try again later") from None
    except (ProviderError, ValueError, KeyError, TypeError):
        raise HTTPException(502, "Mono could not complete this request") from None


async def owned_lookup_session(db, user_id, session_id):
    query = select(BvnLookupSession).where(BvnLookupSession.user_id == user_id)
    if session_id:
        query = query.where(BvnLookupSession.mono_session_id == session_id)
    query = query.order_by(BvnLookupSession.created_at.desc()).limit(1)
    row = lookup_session_or_410((await db.execute(query)).scalar_one_or_none())
    if row.status in {"failed", "initiating"}:
        raise HTTPException(409, "Lookup is not ready; restart after the cooldown")
    return row


@app.post("/onboarding/bvn/start", response_model=api.LookupStartResponse)
async def start_bvn_lookup(
    body: BvnIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await rate_limit("lookup-start:" + str(user.id))
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    recent = (
        await db.execute(
            select(BvnLookupSession)
            .where(
                BvnLookupSession.user_id == user.id,
                BvnLookupSession.created_at >= now_utc() - timedelta(minutes=10),
            )
            .order_by(BvnLookupSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if recent:
        raise HTTPException(429, "BVN lookup recently started; try again later")
    row = BvnLookupSession(
        user_id=user.id,
        mono_session_id="pending:" + str(uuid4()),
        scope="bank_accounts",
        expires_at=now_utc() + timedelta(minutes=10),
        status="initiating",
        created_at=now_utc(),
    )
    db.add(row)
    await db.commit()
    try:
        session_id, methods = await mono_call(lambda: lookup_provider().initiate_lookup(body.bvn))
    except HTTPException:
        row.status = "failed"
        await db.commit()
        raise
    row.mono_session_id = session_id
    row.status = "initiated"
    user.bvn_hash = hash_secret(body.bvn, settings.bvn_pepper)
    user.bvn_last4 = body.bvn[-4:]
    await db.commit()
    return {
        "session_id": session_id,
        "methods": [{"method": x.get("method"), "hint": x.get("hint")} for x in methods],
    }


@app.post("/onboarding/bvn/send-otp", response_model=api.StatusResponse)
async def send_bvn_otp(
    body: BvnMethodIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await rate_limit("lookup-otp:" + str(user.id))
    row = await owned_lookup_session(db, user.id, body.session_id)
    if row.status == "confirmed":
        raise HTTPException(409, "Lookup already confirmed")
    await mono_call(
        lambda: lookup_provider().verify_lookup(row.mono_session_id, body.method, body.phone_number)
    )
    row.status = "otp_sent"
    await db.commit()
    return {"status": "otp_sent"}


@app.post("/onboarding/bvn/confirm", response_model=list[api.DiscoveredAccountResponse])
async def confirm_bvn(
    body: BvnConfirmIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await rate_limit("lookup-confirm:" + str(user.id))
    row = await owned_lookup_session(db, user.id, body.session_id)
    if row.status not in {"otp_sent", "confirmed"}:
        raise HTTPException(409, "Request the BVN OTP before confirming")
    accounts = (
        []
        if row.status == "confirmed"
        else await mono_call(
            lambda: lookup_provider().lookup_details(row.mono_session_id, body.otp)
        )
    )
    for item in accounts:
        institution = item.get("institution") or {}
        number = str(item.get("account_number", ""))
        if not number:
            continue
        values = {
            "account_name": item.get("account_name", "")[:160],
            "account_designation": item.get("account_designation", "")[:40],
            "bank_code": institution.get("bank_code", "")[:10],
            "nip_code": institution.get("nip_code"),
            "institution_name": institution.get("name", "")[:120],
            "account_type": item.get("account_type", "")[:40],
            "account_number_encrypted": encrypt_field(number),
            "account_number_last4": number[-4:],
            "account_number_hash": hash_field(number),
            "status": DiscoveredAccountStatus.discovered,
            "discovered_at": now_utc(),
        }
        existing = (
            await db.execute(
                select(DiscoveredAccount).where(
                    DiscoveredAccount.user_id == user.id,
                    DiscoveredAccount.bank_code == values["bank_code"],
                    DiscoveredAccount.account_number_hash == values["account_number_hash"],
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.status == DiscoveredAccountStatus.linked:
                values.pop("status")
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(DiscoveredAccount(user_id=user.id, provider="mono", **values))
    row.status = "confirmed"
    await db.commit()
    rows = (
        await db.execute(select(DiscoveredAccount).where(DiscoveredAccount.user_id == user.id))
    ).scalars()
    return [
        {
            "id": x.id,
            "account_name": x.account_name,
            "account_designation": x.account_designation,
            "bank_code": x.bank_code,
            "nip_code": x.nip_code,
            "institution_name": x.institution_name,
            "account_type": x.account_type,
            "account_number_last4": x.account_number_last4,
            "status": x.status,
        }
        for x in rows
    ]


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


@app.exception_handler(RequestValidationError)
async def safe_validation_error(_request, exc):
    # Pydantic's default errors echo the input, including BVNs, OTPs and tokens.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(error["loc"]), "type": error["type"], "msg": "Invalid value"}
                for error in exc.errors()
            ]
        },
    )


@app.exception_handler(Exception)
async def safe_internal_error(_request, exc):
    logger.error("request_failed", extra={"error_type": type(exc).__name__})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", response_model=api.HealthResponse)
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


async def rate_limit(key: str) -> None:
    await get_rate_limiter().hit(key)


@app.post("/auth/otp/request", status_code=202, response_model=api.StatusResponse)
async def request_otp(body: PhoneIn, request: Request, db: AsyncSession = Depends(get_db)):
    identifier = body.identifier
    await rate_limit("otp-send:" + identifier)
    await rate_limit("otp-send-ip:" + (request.client.host if request.client else "unknown"))
    await ensure_not_locked(db, identifier)
    if settings.demo_mode and identifier not in settings.demo_identity_allowlist:
        return {"status": "sent"}
    now = now_utc()
    previous = (
        await db.execute(
            select(OtpCode)
            .where(OtpCode.identifier == identifier)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if previous and now - as_utc(previous.created_at) < timedelta(
        seconds=settings.otp_resend_cooldown_seconds
    ):
        raise HTTPException(429, "Try again later")
    code = new_code()
    salt = new_salt()
    try:
        await sender().send(identifier, code)
    except (RuntimeError, OSError) as exc:
        logger.warning("otp_delivery_failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(503, "OTP delivery unavailable") from None
    if previous and previous.consumed_at is None:
        previous.consumed_at = now
    db.add(
        OtpCode(
            identifier=identifier,
            code_hash=code_digest(identifier, code, salt),
            salt=salt,
            expires_at=now + timedelta(seconds=settings.otp_expiry_seconds),
            attempts=0,
            consumed_at=None,
            created_at=now,
        )
    )
    record_auth_event(db, "auth.otp_requested", identifier=identifier)
    await db.commit()
    return {"status": "sent"}


@app.post("/auth/otp/verify", response_model=api.TokenResponse)
async def verify_otp(body: OtpIn, request: Request, db: AsyncSession = Depends(get_db)):
    identifier = body.identifier
    await rate_limit("otp-verify:" + identifier)
    await rate_limit("otp-verify-ip:" + (request.client.host if request.client else "unknown"))
    await ensure_not_locked(db, identifier)
    code_row = (
        await db.execute(
            select(OtpCode)
            .where(OtpCode.identifier == identifier)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    now = now_utc()
    valid = bool(
        code_row
        and code_row.consumed_at is None
        and as_utc(code_row.expires_at) > now
        and code_row.attempts < settings.otp_max_attempts
        and code_matches(identifier, body.otp, code_row.salt, code_row.code_hash)
    )
    if not valid:
        if code_row and code_row.consumed_at is None:
            code_row.attempts += 1
            if code_row.attempts >= settings.otp_max_attempts:
                code_row.consumed_at = now
                forget_code(identifier)
        await register_failure(db, identifier)
        record_auth_event(db, "auth.login_failed", identifier=identifier)
        await db.commit()
        if code_row and as_utc(code_row.expires_at) <= now:
            forget_code(identifier)
        raise HTTPException(401, "Invalid code")
    code_row.consumed_at = now
    await clear_failures(db, identifier)
    forget_code(identifier)
    condition = User.phone == body.phone if body.phone else User.email == str(body.email)
    user = (await db.execute(select(User).where(condition))).scalar_one_or_none()
    if not user:
        user = User(
            phone=body.phone,
            email=str(body.email) if body.email else None,
            bvn_hash=None,
            bvn_last4=None,
            created_at=now,
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
    record_auth_event(db, "auth.login", user_id=user.id, identifier=identifier)
    await db.commit()
    return {"access_token": access_token(user.id), "refresh_token": raw, "token_type": "bearer"}


@app.get("/dev/otp-inbox", include_in_schema=False)
async def dev_otp_inbox(
    identifier: str,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(presenter_auth),
):
    if settings.demo_mode:
        require_presenter(credentials)
        if identifier not in settings.demo_identity_allowlist:
            raise HTTPException(404, "Not found")
        return {"code": inbox_code(identifier)}
    client_host = request.client.host if request.client else ""
    try:
        loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        loopback = False
    local_host = request.url.hostname in {"localhost", "127.0.0.1", "::1", "testserver"}
    if not (
        loopback
        and local_host
        and settings.environment != "production"
        and settings.otp_dev_inbox_enabled
    ):
        raise HTTPException(404, "Not found")
    return {"code": inbox_code(identifier)}


def require_presenter(credentials: HTTPBasicCredentials | None) -> None:
    if (
        not settings.demo_mode
        or settings.environment == "production"
        or not settings.demo_otp_inbox_password
    ):
        raise HTTPException(404, "Not found")
    if not credentials or not (
        hmac.compare_digest(credentials.username.encode(), b"demo")
        and hmac.compare_digest(
            credentials.password.encode(), settings.demo_otp_inbox_password.encode()
        )
    ):
        raise HTTPException(
            401, "Presenter authentication required", headers={"WWW-Authenticate": "Basic"}
        )


@app.get("/dev/otp-inbox/page", include_in_schema=False, response_class=HTMLResponse)
async def presenter_otp_page(
    identifier: str = "",
    credentials: HTTPBasicCredentials | None = Depends(presenter_auth),
):
    require_presenter(credentials)
    if identifier and identifier not in settings.demo_identity_allowlist:
        raise HTTPException(404, "Not found")
    options = "".join(
        f'<option value="{escape(item, quote=True)}"'
        + (" selected" if item == identifier else "")
        + f">{escape(item)}</option>"
        for item in sorted(settings.demo_identity_allowlist)
    )
    code = inbox_code(identifier) if identifier else None
    content = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Demo OTP inbox</title>'
        "<h1>Demo login OTP</h1><p>Request a code from the mobile app, then refresh this page.</p>"
        f'<form method="get"><select name="identifier">{options}</select>'
        "<button>Refresh</button></form>"
        f"<p>{escape(code) if code else 'No active code.'}</p>"
        "</html>"
    )
    return HTMLResponse(
        content,
        headers={
            "Content-Security-Policy": "default-src 'none'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        },
    )


@app.post("/auth/refresh", response_model=api.TokenResponse)
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
        selector = (
            RefreshToken.family_id == row.family_id if row.family_id else RefreshToken.id == row.id
        )
        family = (
            await db.execute(
                select(RefreshToken).where(selector, RefreshToken.user_id == row.user_id)
            )
        ).scalars()
        for token in family:
            token.revoked_at = now
        await db.commit()
        raise HTTPException(401, "Invalid refresh token")
    if row.revoked_at or as_utc(row.expires_at) <= now:
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
        selector = (
            RefreshToken.family_id == row.family_id if row.family_id else RefreshToken.id == row.id
        )
        family = (
            await db.execute(select(RefreshToken).where(selector, RefreshToken.user_id == user.id))
        ).scalars()
        for token in family:
            token.revoked_at = now_utc()
        record_auth_event(db, "auth.logout", user_id=user.id)
        await db.commit()


@app.post("/auth/logout-all", status_code=204)
async def logout_all(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    now = now_utc()
    user.sessions_revoked_at = now
    tokens = (
        await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars()
    for token in tokens:
        token.revoked_at = now
    record_auth_event(db, "auth.logout_all", user_id=user.id)
    await db.commit()


@app.post("/identity/bvn/verify")
async def verify_bvn(
    body: BvnIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if settings.environment == "production" or settings.aggregator_provider != "mock":
        raise HTTPException(404, "Not found")
    user.bvn_hash = hash_secret(body.bvn, settings.bvn_pepper)
    user.bvn_last4 = body.bvn[-4:]
    await db.commit()
    return {
        "verified": True,
        "profile": {"name": f"Demo Customer {body.bvn[-2:]}", "bvn_last4": body.bvn[-4:]},
    }


@app.post("/consents", status_code=201, response_model=api.ConsentCreatedResponse)
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


@app.get("/consents", response_model=list[api.ConsentResponse])
async def consents(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Consent).where(Consent.user_id == user.id))).scalars()
    return [
        {"id": x.id, "institution": x.institution, "scope": x.scope, "revoked_at": x.revoked_at}
        for x in rows
    ]


@app.delete("/consents/{consent_id}", status_code=204)
async def revoke(
    consent_id: UUID,
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
        accounts_to_purge = (
            (
                await db.execute(
                    select(Account).where(
                        Account.user_id == user.id, Account.consent_id == consent.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if links:
            for account in accounts_to_purge:
                await purge_linked_account(db, account, links[0])
        for link in links:
            link.status = (
                "pending_unlink"
                if link.provider == "mono" and link.provider_account_id
                else "unlinked"
            )
        await db.execute(delete(InsightRecord).where(InsightRecord.user_id == user.id))
        await db.commit()
        for link in links:
            if link.status == "pending_unlink":
                await retry_pending_link(db, link)
        await db.commit()


@app.post("/accounts/link", status_code=201, response_model=api.MockLinkResponse)
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
                if (user.phone or "").endswith("001")
                else "freelancer"
                if (user.phone or "").endswith("002")
                else "student"
                if (user.phone or "").endswith("003")
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


@app.post("/accounts/link/initiate", status_code=201, response_model=api.InitiateLinkResponse)
async def initiate_link(
    body: InitiateIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await rate_limit("link:" + str(user.id))
    if settings.aggregator_provider != "mono":
        raise HTTPException(409, "Mono linking is disabled")
    await require_live_sync(db, user.id, now_utc(), new_account=True)
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
    url = await mono_call(
        lambda: provider().initiate(
            body.name, str(body.email), str(link.id), settings.mono_redirect_url
        )
    )
    await db.commit()
    record_auth_event(db, "link.initiated", user_id=user.id)
    return {"ref": link.id, "url": url, "status": "pending"}


@app.get("/accounts/link/status", response_model=api.LinkStatusResponse)
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
    account_id = (
        await db.execute(
            select(Account.id).where(
                Account.user_id == user.id, Account.consent_id == link.consent_id
            )
        )
    ).scalar_one_or_none()
    return {
        "ref": link.id,
        "status": link.status,
        "data_status": link.data_status,
        "account_id": account_id,
    }


@app.post("/accounts/link/exchange", response_model=api.ExchangeLinkResponse)
async def exchange_link(
    body: ExchangeIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if settings.aggregator_provider != "mono":
        raise HTTPException(409, "Mono linking is disabled")
    await require_live_sync(db, user.id, now_utc(), new_account=True)
    await owned_consent(db, user.id, body.consent_id)
    provider_id = await mono_call(lambda: provider().exchange(body.code))
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
    record_auth_event(db, "link.exchanged", user_id=user.id)
    return {"ref": link.id, "status": "connected"}


async def process_mono_event(event: dict, event_key: str | None = None):
    """Claim one delivery; keep failed events eligible for a later redelivery."""
    if event_key is None:
        return await apply_mono_event(event)
    token = str(uuid4())
    async with SessionLocal() as db:
        claimed = await db.execute(
            update(WebhookEvent)
            .where(
                WebhookEvent.event_key == event_key,
                or_(
                    WebhookEvent.processing_status.in_(["pending", "failed"]),
                    and_(
                        WebhookEvent.processing_status == "processing",
                        WebhookEvent.processing_started_at < now_utc() - timedelta(minutes=2),
                    ),
                ),
            )
            .values(
                processing_status="processing",
                processing_started_at=now_utc(),
                processing_token=token,
            )
        )
        await db.commit()
        if not claimed.rowcount:
            return
    status = "processed"
    try:
        await apply_mono_event(event)
    except Exception as exc:
        status = "failed"
        logger.warning("mono_webhook_processing_failed", extra={"error_type": type(exc).__name__})
    async with SessionLocal() as db:
        await db.execute(
            update(WebhookEvent)
            .where(
                WebhookEvent.event_key == event_key,
                WebhookEvent.processing_token == token,
            )
            .values(
                processing_status=status, processed_at=now_utc() if status == "processed" else None
            )
        )
        await db.commit()


async def apply_mono_event(event: dict):
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
                        ProviderLink.provider_account_id_hash == hash_field(str(account_id)),
                    )
                )
            ).scalar_one_or_none()
        if link is None:
            return
        consent = await db.get(Consent, link.consent_id)
        if consent is None:
            return
        if name == "mono.events.account_unlinked":
            if link.status == "unlinked":
                return
            accounts_to_purge = (
                (
                    await db.execute(
                        select(Account).where(
                            Account.user_id == link.user_id, Account.consent_id == consent.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            for account in accounts_to_purge:
                await purge_linked_account(db, account, link)
            link.status = "unlinked"
            link.provider_account_id = None
            if consent.revoked_at is None:
                consent.revoked_at = now_utc()
                db.add(
                    ConsentAudit(
                        consent_id=consent.id,
                        event="revoked_by_provider",
                        actor="mono",
                        at=consent.revoked_at,
                    )
                )
            await db.commit()
            record_auth_event(db, "link.unlinked_by_provider", user_id=link.user_id)
            return
        if consent.revoked_at or as_utc(consent.expires_at) <= now_utc():
            return
        link.last_webhook_at = now_utc()
        discovered = (
            await db.execute(
                select(DiscoveredAccount).where(DiscoveredAccount.link_ref == str(link.id))
            )
        ).scalar_one_or_none()
        if name not in {"mono.events.account_connected", "mono.events.account_updated"}:
            return
        if name == "mono.events.account_connected" and link.data_status in {
            "AVAILABLE",
            "PARTIAL",
            "UNAVAILABLE",
            "FAILED",
        }:
            return
        if account_id and link.provider_account_id and link.provider_account_id != str(account_id):
            raise ValueError("Webhook account identifier mismatch")
        if account_id:
            link.provider_account_id = str(account_id)
            link.status = "connected"
        if name == "mono.events.account_connected":
            link.data_status = "PROCESSING"
            if discovered:
                discovered.status = DiscoveredAccountStatus.linked
            await db.commit()
            record_auth_event(db, "link.connected", user_id=link.user_id)
            return
        link.data_status = str(meta.get("data_status") or "PROCESSING").upper()
        if (
            discovered
            and discovered.account_match_requested
            and account_data.get("account_match") is not True
        ):
            link.status = "mismatch"
            await db.commit()
            return
        if link.data_status not in {"AVAILABLE", "PARTIAL"} or not link.provider_account_id:
            await db.execute(
                update(Account)
                .where(Account.consent_id == consent.id, Account.user_id == link.user_id)
                .values(sync_status=SyncStatus.delayed)
            )
            await db.commit()
            return
        info = account_data
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
            account_category, _ = category_for_institution(institution.code, institution.name)
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
                available_balance_minor=(
                    int(info["balance"])
                    if "balance" in (meta.get("retrieved_data") or [])
                    and info.get("balance") is not None
                    else None
                ),
                balance_synced_at=(
                    now_utc()
                    if "balance" in (meta.get("retrieved_data") or [])
                    and info.get("balance") is not None
                    else None
                ),
                sync_status=SyncStatus.ok,
                category=account_category,
            )
            db.add(account)
            await db.flush()
        else:
            if "balance" in (meta.get("retrieved_data") or []) and info.get("balance") is not None:
                account.current_balance_minor = int(info["balance"])
                account.available_balance_minor = account.current_balance_minor
                account.balance_synced_at = now_utc()
                account.sync_status = SyncStatus.ok
        await db.commit()
        if "transactions" not in (meta.get("retrieved_data") or []) or account.sync_paused:
            return
        local_account_id = account.id
        try:
            await sync_owned_account(db, account, link, now_utc())
            await db.commit()
        except (ProviderNotReady, ProviderUnavailable, HTTPException):
            await db.rollback()
            account = await db.get(Account, local_account_id)
            if account:
                account.sync_status = SyncStatus.delayed
                await db.commit()
            raise


@app.post("/webhooks/mono", response_model=api.WebhookResponse)
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
        existing = (
            await db.execute(select(WebhookEvent).where(WebhookEvent.event_key == event_key))
        ).scalar_one_or_none()
        if existing and existing.processing_status == "processed":
            return {"received": True}
        if existing is None:
            db.add(
                WebhookEvent(
                    event_key=event_key, event_name=event["event"][:100], received_at=now_utc()
                )
            )
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
    if event["event"] in {
        "mono.events.account_connected",
        "mono.events.account_updated",
        "mono.events.account_unlinked",
    }:
        background.add_task(process_mono_event, event, event_key)
    return {"received": True}


@app.post("/accounts/discovered/select", response_model=api.SelectionResponse)
async def select_discovered_accounts(
    body: SelectDiscoveredIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    selected = set(body.ids)
    rows = (
        (await db.execute(select(DiscoveredAccount).where(DiscoveredAccount.user_id == user.id)))
        .scalars()
        .all()
    )
    if not selected.issubset({row.id for row in rows}):
        raise HTTPException(404, "Discovered account not found")
    for row in rows:
        if row.status == DiscoveredAccountStatus.linked:
            continue
        row.status = (
            DiscoveredAccountStatus.discovered
            if row.id in selected
            else DiscoveredAccountStatus.skipped
        )
    await db.commit()
    return {
        "selected": len(selected),
        "skipped": sum(row.status == DiscoveredAccountStatus.skipped for row in rows),
    }


@app.get("/accounts/skipped", response_model=list[api.SkippedAccountResponse])
async def skipped_accounts(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        (
            await db.execute(
                select(DiscoveredAccount).where(
                    DiscoveredAccount.user_id == user.id,
                    DiscoveredAccount.status == DiscoveredAccountStatus.skipped,
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "institution_name": row.institution_name,
            "account_type": row.account_type,
            "account_number_last4": row.account_number_last4,
        }
        for row in rows
    ]


async def link_discovered_account(
    row_id: UUID,
    body: LinkDiscoveredIn,
    user: User,
    db: AsyncSession,
    skipped_only: bool = False,
):
    await rate_limit("link:" + str(user.id))
    if settings.aggregator_provider != "mono":
        raise HTTPException(409, "Mono linking is disabled")
    row = (
        await db.execute(
            select(DiscoveredAccount).where(
                DiscoveredAccount.id == row_id, DiscoveredAccount.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status == DiscoveredAccountStatus.linked:
        raise HTTPException(404, "Discovered account not found")
    if skipped_only and row.status != DiscoveredAccountStatus.skipped:
        raise HTTPException(404, "Skipped account not found")
    if row.link_ref:
        raise HTTPException(409, "A link is already pending for this account")
    institution = await mono_call(lambda: resolve_institution(row))
    consent = Consent(
        user_id=user.id,
        institution=row.institution_name[:80],
        scope="auth",
        granted_at=now_utc(),
        expires_at=now_utc() + timedelta(days=30),
        revoked_at=None,
    )
    db.add(consent)
    await db.flush()
    link = ProviderLink(
        user_id=user.id,
        consent_id=consent.id,
        provider="mono",
        provider_account_id=None,
        status="pending",
        data_status="PROCESSING",
        created_at=now_utc(),
        last_webhook_at=None,
    )
    db.add(link)
    await db.flush()
    ref = str(link.id)
    account_number = (
        decrypt_field(row.account_number_encrypted)
        if settings.mono_account_match_enabled and institution
        else None
    )
    url = await mono_call(
        lambda: provider().initiate(
            row.account_name,
            str(body.email),
            ref,
            settings.mono_redirect_url,
            institution=institution,
            account_number=account_number,
        )
    )
    row.link_ref = ref
    row.institution_id = institution["id"] if institution else None
    row.institution_auth_method = institution["auth_method"] if institution else None
    row.account_match_requested = account_number is not None
    await db.commit()
    return {"ref": ref, "mono_url": url, "institution_mapped": institution is not None}


@app.post("/accounts/discovered/{row_id}/link", response_model=api.HostedLinkResponse)
async def link_selected_account(
    row_id: UUID,
    body: LinkDiscoveredIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await link_discovered_account(row_id, body, user, db)


@app.post("/accounts/skipped/{row_id}/link", response_model=api.HostedLinkResponse)
async def link_skipped_account(
    row_id: UUID,
    body: LinkDiscoveredIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await link_discovered_account(row_id, body, user, db, skipped_only=True)


@app.get("/accounts", response_model=api.AccountsResponse)
async def accounts(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = (
        select(Account, Institution)
        .join(Consent, Account.consent_id == Consent.id)
        .join(Institution, Account.institution_id == Institution.id)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    groups = {
        category.value: {"count": 0, "totals_minor_by_currency": {}, "accounts": []}
        for category in AccountCategory
    }
    links = {
        link.consent_id: link
        for link in (
            await db.execute(select(ProviderLink).where(ProviderLink.user_id == user.id))
        ).scalars()
    }
    for account, institution in (await db.execute(q)).all():
        derived_category, category_unmapped = category_for_institution(
            institution.code, institution.name
        )
        category = account.category if category_unmapped else derived_category
        group = groups[category.value]
        group["count"] += 1
        totals = group["totals_minor_by_currency"]
        totals[account.currency] = totals.get(account.currency, 0) + account.current_balance_minor
        group["accounts"].append(
            {
                "id": account.id,
                "institution": institution.name,
                "type": account.type,
                "currency": account.currency,
                "balance_minor": account.current_balance_minor,
                "account_number_masked": account.account_number_masked,
                "category_unmapped": category_unmapped,
                "available_balance_minor": account.available_balance_minor,
                "ledger_balance_minor": account.ledger_balance_minor,
                "sync_paused": account.sync_paused,
                "data_status": links[account.consent_id].data_status
                if account.consent_id in links
                else None,
                **balance_state(account, now_utc(), settings.balance_stale_minutes),
            }
        )
    return {"groups": groups}


@app.get("/accounts/{account_id}", response_model=api.AccountDetailResponse)
async def account_detail(
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
    institution = await db.get(Institution, account.institution_id)
    derived_category, category_unmapped = category_for_institution(
        institution.code, institution.name
    )
    link = (
        await db.execute(
            select(ProviderLink).where(
                ProviderLink.user_id == user.id,
                ProviderLink.consent_id == account.consent_id,
            )
        )
    ).scalar_one_or_none()
    return {
        "id": account.id,
        "account_number_masked": account.account_number_masked,
        "type": account.type,
        "category": account.category if category_unmapped else derived_category,
        "category_unmapped": category_unmapped,
        "currency": account.currency,
        "available_balance_minor": account.available_balance_minor,
        "ledger_balance_minor": account.ledger_balance_minor,
        **balance_state(account, now_utc(), settings.balance_stale_minutes),
        "sync_paused": account.sync_paused,
        "data_status": link.data_status if link else None,
    }


@app.post("/accounts/{account_id}/pause", response_model=api.PauseResponse)
async def pause_account_sync(
    account_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    account = (
        await db.execute(
            select(Account).where(Account.id == account_id, Account.user_id == user.id)
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Account not found")
    account.sync_paused = True
    await db.commit()
    return {"sync_paused": True}


@app.post("/accounts/{account_id}/resume", response_model=api.PauseResponse)
async def resume_account_sync(
    account_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    account = (
        await db.execute(
            select(Account).where(Account.id == account_id, Account.user_id == user.id)
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Account not found")
    account.sync_paused = False
    await db.commit()
    return {"sync_paused": False}


@app.post("/accounts/{account_id}/unlink", response_model=api.UnlinkResponse)
async def unlink_account(
    account_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    account = (
        await db.execute(
            select(Account).where(Account.id == account_id, Account.user_id == user.id)
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Account not found")
    link = (
        await db.execute(
            select(ProviderLink).where(
                ProviderLink.user_id == user.id,
                ProviderLink.consent_id == account.consent_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(404, "Link not found")
    await purge_linked_account(db, account, link)
    await db.commit()
    if link.status == "pending_unlink":
        await retry_pending_link(db, link)
        await db.commit()
    return {"status": link.status, "local_data_purged": True}


def sync_window_start(last_synced_at: datetime | None, now: datetime) -> datetime:
    return (
        as_utc(last_synced_at) - timedelta(days=3) if last_synced_at else now - timedelta(days=190)
    )


async def sync_owned_account(
    db: AsyncSession, account: Account, link: ProviderLink, now: datetime
) -> int:
    """Fetch a bounded provider window and rebuild derived user data."""
    await owned_consent(db, account.user_id, account.consent_id)
    if link.status != "connected" or account.sync_paused:
        raise HTTPException(409, "Account is not connected")
    if link.provider == "mono":
        await require_live_sync(db, account.user_id, now)
    try:
        start = sync_window_start(account.sync_cursor_at or account.last_synced_at, now)
        rows = await provider().transactions(link.provider_account_id, start, now)
    except ProviderNotReady as exc:
        raise HTTPException(409, "Provider data is not ready") from exc
    except ProviderUnavailable as exc:
        raise HTTPException(503, "Provider temporarily unavailable") from exc
    if len(rows) > 10_000:
        raise HTTPException(502, "Provider returned too many transactions")
    count = await ingest(db, account, rows)
    account.sync_cursor_at = now
    account.last_synced_at = now
    await db.flush()
    await rebuild_account(db, account.id, account.user_id, now)
    await db.flush()
    await sync_detected_obligations(db, account.user_id)
    await db.flush()
    await db.execute(
        delete(InsightRecord).where(
            InsightRecord.user_id == account.user_id, InsightRecord.dismissed_at.is_(None)
        )
    )
    await run_for_user(db, account.user_id, now)
    return count


@app.post("/sync", response_model=api.SyncResponse)
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
                Account.sync_paused.is_(False),
            )
        )
    ).all()
    count = 0
    for account, link in pairs:
        count += await sync_owned_account(db, account, link, now)
    await db.commit()
    return {"accounts_synced": len(pairs), "transactions_imported": count}


@app.post(
    "/accounts/{account_id}/refresh",
    response_model=api.RefreshResponse,
    response_model_exclude_unset=True,
)
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
    if link.provider == "mono":
        await require_live_sync(db, user.id, now_utc())
    if account.sync_paused:
        raise HTTPException(409, "Sync is paused for this account")
    if link.provider == "mono" and link.data_status not in {"AVAILABLE", "PARTIAL"}:
        account.sync_status = SyncStatus.delayed
        await db.commit()
        return {
            "status": "delayed",
            "cached_balance_minor": account.current_balance_minor,
            **balance_state(account, now_utc(), settings.balance_stale_minutes),
        }
    cooldown = settings.account_refresh_cooldown_seconds
    if link.provider == "mono":
        cooldown = max(cooldown, 300)
    elapsed = time.monotonic() - _refresh_requests.get(account.id, -float("inf"))
    if account.last_synced_at:
        elapsed = min(elapsed, (now_utc() - as_utc(account.last_synced_at)).total_seconds())
    if elapsed < cooldown:
        wait = max(1, int(cooldown - elapsed) + 1)
        raise HTTPException(429, "Refresh cooldown active", headers={"Retry-After": str(wait)})
    _refresh_requests[account.id] = time.monotonic()
    if link.provider == "mono":
        await reserve_refresh_call(
            db, user.id, account.id, settings.mono_refresh_monthly_limit
        )
        try:
            response = await provider().balance(link.provider_account_id, realtime=True)
        except (ProviderError, ValueError, KeyError, TypeError):
            account.sync_status = SyncStatus.delayed
            await db.commit()
            return {
                "status": "delayed",
                "cached_balance_minor": account.current_balance_minor,
                **balance_state(account, now_utc(), settings.balance_stale_minutes),
            }
        data = response.get("data") or {}
        job = response.get("_realtime") or {}
        job_status = job.get("job_status")
        if job_status in {"processing", "failed"}:
            if job_status == "failed":
                account.sync_status = SyncStatus.delayed
                await db.commit()
            return {
                "status": "requested" if job_status == "processing" else "delayed",
                "job_status": job_status,
                "cached_balance_minor": account.current_balance_minor,
                **balance_state(account, now_utc(), settings.balance_stale_minutes),
            }
        if job.get("has_new_data") == "false":
            return {
                "status": "cached",
                "cached_balance_minor": account.current_balance_minor,
                **balance_state(account, now_utc(), settings.balance_stale_minutes),
            }
        if (
            isinstance(data, dict)
            and type(data.get("balance")) is int
            and data.get("currency", "NGN") == account.currency
        ):
            account.current_balance_minor = data["balance"]
            account.available_balance_minor = data["balance"]
            account.balance_synced_at = now_utc()
            account.sync_status = SyncStatus.ok
            await db.commit()
            status = "synced"
        else:
            status = "requested"
        return {
            "status": status,
            "cached_balance_minor": account.current_balance_minor,
            **balance_state(account, now_utc(), settings.balance_stale_minutes),
        }
    count = await sync_owned_account(db, account, link, now_utc())
    account.balance_synced_at = now_utc()
    account.available_balance_minor = account.current_balance_minor
    account.sync_status = SyncStatus.ok
    await db.commit()
    return {
        "status": "synced",
        "transactions_imported": count,
        **balance_state(account, now_utc(), settings.balance_stale_minutes),
    }


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


def manual_asset_response(row: ManualAsset) -> dict:
    return {
        "id": row.id,
        "platform": row.platform,
        "category": row.category,
        "currency": row.currency,
        "amount_minor": row.amount_minor,
        "fx_rate_used_ppm": row.fx_rate_used,
        "value_ngn_minor": asset_value_ngn_minor(row),
        "update_cadence": row.update_cadence,
        "last_updated_at": row.last_updated_at,
        "next_reminder_at": row.next_reminder_at,
    }


@app.get("/assets", response_model=list[api.ManualAssetResponse])
async def list_manual_assets(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    rows = (
        (await db.execute(select(ManualAsset).where(ManualAsset.user_id == user.id)))
        .scalars()
        .all()
    )
    return [manual_asset_response(row) for row in rows]


@app.post("/assets", status_code=201, response_model=api.ManualAssetResponse)
async def create_manual_asset(
    body: ManualAssetIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    rate = RATE_SCALE
    if body.currency == "USD":
        rate, _ = await get_usd_ngn_rate(db, body.fx_rate)
    now = now_utc()
    row = ManualAsset(
        user_id=user.id,
        platform=body.platform,
        category=body.category,
        currency=body.currency,
        amount_minor=body.amount_minor,
        fx_rate_used=rate,
        update_cadence=body.update_cadence,
        last_updated_at=now,
        next_reminder_at=next_reminder(now, body.update_cadence),
    )
    db.add(row)
    await db.commit()
    return manual_asset_response(row)


@app.put("/assets/{asset_id}", response_model=api.ManualAssetResponse)
async def update_manual_asset(
    asset_id: UUID,
    body: ManualAssetIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(ManualAsset).where(ManualAsset.id == asset_id, ManualAsset.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Asset not found")
    rate = RATE_SCALE
    if body.currency == "USD":
        rate, _ = await get_usd_ngn_rate(db, body.fx_rate)
    now = now_utc()
    row.platform = body.platform
    row.category = body.category
    row.currency = body.currency
    row.amount_minor = body.amount_minor
    row.fx_rate_used = rate
    row.update_cadence = body.update_cadence
    row.last_updated_at = now
    row.next_reminder_at = next_reminder(now, body.update_cadence)
    await db.commit()
    return manual_asset_response(row)


@app.delete("/assets/{asset_id}", status_code=204)
async def delete_manual_asset(
    asset_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        delete(ManualAsset).where(ManualAsset.id == asset_id, ManualAsset.user_id == user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Asset not found")
    await db.commit()


@app.get("/net-position", response_model=api.NetPositionResponse)
async def net_position(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    linked = (
        await db.execute(
            select(Account, Institution)
            .join(Institution, Account.institution_id == Institution.id)
            .join(Consent, Account.consent_id == Consent.id)
            .join(ProviderLink, ProviderLink.consent_id == Account.consent_id)
            .where(
                Account.user_id == user.id,
                ProviderLink.user_id == user.id,
                ProviderLink.status == "connected",
                Account.currency == "NGN",
                Consent.revoked_at.is_(None),
                Consent.expires_at > now_utc(),
            )
        )
    ).all()
    cash = sum(
        account.current_balance_minor
        for account, _ in linked
        if account.category != AccountCategory.investment
    )
    linked_investments = sum(
        account.current_balance_minor
        for account, _ in linked
        if account.category == AccountCategory.investment
    )
    assets = (
        (await db.execute(select(ManualAsset).where(ManualAsset.user_id == user.id)))
        .scalars()
        .all()
    )
    usd_assets = [asset for asset in assets if asset.currency == "USD"]
    read_rate: int | None = None
    fx_rate_warning = False
    if usd_assets:
        try:
            read_rate, _ = await get_usd_ngn_rate(db, None)
            await db.commit()
        except HTTPException:
            fx_rate_warning = True
    asset_values = {
        asset.id: (
            convert_minor(asset.amount_minor, read_rate)
            if asset.currency == "USD" and read_rate is not None
            else asset_value_ngn_minor(asset)
        )
        for asset in assets
    }
    investments = linked_investments + sum(asset_values.values())
    breakdown = [
        {
            "id": account.id,
            "source": "account",
            "label": institution.name,
            "value_ngn_minor": account.current_balance_minor,
            "currency": account.currency,
            "paused": account.sync_paused,
            "fx_rate_ppm": None,
        }
        for account, institution in linked
    ] + [
        {
            "id": asset.id,
            "source": "manual_asset",
            "label": asset.platform.value,
            "value_ngn_minor": asset_values[asset.id],
            "currency": asset.currency,
            "paused": False,
            "fx_rate_ppm": read_rate if asset.currency == "USD" else None,
        }
        for asset in assets
    ]
    return {
        "cash_minor": cash,
        "investments_minor": investments,
        "total_minor": cash + investments,
        "currency": "NGN",
        "as_of": now_utc(),
        "fx_rate_warning": fx_rate_warning,
        "paused_accounts_included": sum(account.sync_paused for account, _ in linked),
        "breakdown": breakdown,
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


@app.get("/transactions", response_model=list[api.TransactionResponse])
async def transactions(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
    account_id: UUID | None = None,
    merchant_id: UUID | None = None,
    merchant: str | None = Query(default=None, min_length=1, max_length=100),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    type: Literal["credit", "debit"] | None = None,
    limit: int = 50,
    offset: int = 0,
):
    from_date, to_date = as_utc(from_date), as_utc(to_date)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise HTTPException(422, "Invalid pagination")
    if from_date and to_date and (to_date < from_date or to_date - from_date > timedelta(days=365)):
        raise HTTPException(422, "Invalid date range")
    known_categories = FETCH_CATEGORIES | set(CATEGORY_ALIASES) | set(CATEGORY_ALIASES.values())
    if category and category not in known_categories:
        raise HTTPException(422, "Invalid category")
    active = (
        select(Account.id)
        .join(Consent)
        .where(
            Account.user_id == user.id, Consent.revoked_at.is_(None), Consent.expires_at > now_utc()
        )
    )
    q = select(Transaction).where(Transaction.account_id.in_(active))
    if category:
        labels = [category, *(key for key, value in CATEGORY_ALIASES.items() if value == category)]
        q = q.where(Transaction.category.in_(labels))
    q = q.where(Transaction.account_id == account_id) if account_id else q
    q = q.where(Transaction.merchant_id == merchant_id) if merchant_id else q
    if merchant:
        q = q.outerjoin(Merchant, Transaction.merchant_id == Merchant.id).where(
            or_(
                Transaction.decoded_merchant.ilike(f"%{merchant}%"),
                Merchant.canonical_name.ilike(f"%{merchant}%"),
            )
        )
    q = q.where(Transaction.posted_at >= from_date) if from_date else q
    q = q.where(Transaction.posted_at <= to_date) if to_date else q
    q = q.where(Transaction.direction == Direction(type)) if type else q
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
            "raw_narration": x.narration_raw,
            "decoded_merchant": x.decoded_merchant,
            "category": category_label(x.category),
            "category_source": x.category_source,
        }
        for x in rows
    ]


@app.get("/transactions/recent", response_model=list[api.RecentTransactionResponse])
async def recent_transactions(
    limit: int = 5, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if not 1 <= limit <= 20:
        raise HTTPException(422, "Limit must be between 1 and 20")
    rows = (
        await db.execute(
            select(Transaction, Account, Institution)
            .join(Account, Transaction.account_id == Account.id)
            .join(Institution, Account.institution_id == Institution.id)
            .where(Account.id.in_(active_accounts(user.id, now_utc())))
            .order_by(Transaction.posted_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": tx.id,
            "account_id": account.id,
            "account_name": None,
            "masked_number": account.account_number_masked,
            "institution": institution.name,
            "decoded_merchant": tx.decoded_merchant,
            "amount_minor": tx.amount_minor,
            "direction": tx.direction,
            "category": category_label(tx.category),
            "posted_at": tx.posted_at,
        }
        for tx, account, institution in rows
    ]


@app.patch("/transactions/{transaction_id}/category", response_model=api.ReclassificationResponse)
async def reclassify_transaction(
    transaction_id: UUID,
    body: ReclassifyIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = (
        await db.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Transaction.id == transaction_id, Account.user_id == user.id)
        )
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    if not body.apply_to_future:
        tx.category = body.category
        tx.category_source = CategorySource.manual
        db.add(ClassificationCorrection(
            user_id=user.id,
            counterparty_key=counterparty_key(tx.decoded_merchant or tx.narration_clean),
            category=body.category,
            created_at=now_utc(),
        ))
        await db.commit()
        return {"id": tx.id, "category": tx.category, "category_source": tx.category_source}
    key = counterparty_key(tx.decoded_merchant or tx.narration_clean)
    if not key:
        raise HTTPException(422, "Transaction has no counterparty for a future rule")
    rule = (
        await db.execute(
            select(CategoryRule).where(
                CategoryRule.user_id == user.id, CategoryRule.counterparty_key == key
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        db.add(
            CategoryRule(
                user_id=user.id, counterparty_key=key, category=body.category, created_at=now_utc()
            )
        )
    else:
        rule.category = body.category
    db.add(ClassificationCorrection(
        user_id=user.id, counterparty_key=key, category=body.category, created_at=now_utc()
    ))
    matching = (
        await db.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == user.id)
        )
    ).scalars()
    for item in matching:
        if counterparty_key(item.decoded_merchant or item.narration_clean) == key:
            item.category = body.category
            item.category_source = CategorySource.user_rule
    await db.commit()
    return {"id": tx.id, "category": tx.category, "category_source": tx.category_source}


@app.get("/category-rules", response_model=list[api.CategoryRuleResponse])
async def category_rules(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(CategoryRule).where(CategoryRule.user_id == user.id))).scalars()
    return [
        {"id": row.id, "counterparty_key": row.counterparty_key, "category": row.category}
        for row in rows
    ]


@app.post("/classification-corrections/{correction_id}/confirm")
async def confirm_classification_correction(
    correction_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    correction = (
        await db.execute(
            select(ClassificationCorrection).where(
                ClassificationCorrection.id == correction_id,
                ClassificationCorrection.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if correction is None:
        raise HTTPException(404, "Correction not found")
    correction.confirmed = True
    await db.commit()
    return {"id": correction.id, "confirmed": correction.confirmed}


@app.delete("/category-rules/{rule_id}", status_code=204)
async def delete_category_rule(
    rule_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        delete(CategoryRule).where(CategoryRule.id == rule_id, CategoryRule.user_id == user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Category rule not found")
    await db.commit()


@app.get("/analytics/spending", response_model=api.SpendingResponse)
async def spending_analytics(
    period: Literal["this_month", "last_month", "custom"] = "this_month",
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    today = now_utc().date()
    if period == "custom":
        if from_date is None or to_date is None or to_date < from_date:
            raise HTTPException(422, "A valid from/to range is required")
        if (to_date - from_date).days > 366:
            raise HTTPException(422, "Date range is too long")
        start_day, end_day = from_date, to_date
    elif period == "last_month":
        end_day = today.replace(day=1) - timedelta(days=1)
        start_day = end_day.replace(day=1)
    else:
        start_day, end_day = today.replace(day=1), today
    start = datetime.combine(start_day, datetime.min.time(), UTC)
    end = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), UTC)
    amounts = (
        await db.execute(
            select(Transaction.category, func.sum(Transaction.amount_minor))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user.id,
                Account.currency == "NGN",
                Account.id.in_(active_accounts(user.id, now_utc())),
                Transaction.direction == Direction.debit,
                Transaction.posted_at >= start,
                Transaction.posted_at < end,
            )
            .group_by(Transaction.category)
        )
    ).all()
    normalised = {}
    for category, amount in amounts:
        label = category_label(category)
        normalised[label] = normalised.get(label, 0) + amount
    amounts = list(normalised.items())
    total = sum(amount for _, amount in amounts)
    return {
        "period": period,
        "from": start_day,
        "to": end_day,
        "total_outflow_minor": total,
        "categories": [
            {
                "category": category,
                "amount_minor": amount,
                "percentage": round(amount * 100 / total, 2) if total else 0,
            }
            for category, amount in sorted(amounts)
        ],
        "own_transfers_excluded": 0,
        "own_transfer_detection": "not_available",
    }


@app.get("/budget", response_model=api.BudgetResponse)
async def get_budget(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(Budget)
            .where(Budget.user_id == user.id, Budget.effective_from <= now_utc())
            .order_by(Budget.effective_from.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return {"monthly_limit_minor": None, "effective_from": None}
    return {"monthly_limit_minor": row.monthly_limit_minor, "effective_from": row.effective_from}


@app.get("/privacy-preferences", response_model=api.PrivacyPreferenceResponse)
async def get_privacy_preferences(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = await db.get(UserSettings, user.id)
    return {"privacy_blur": row.privacy_blur if row else False}


@app.put("/privacy-preferences", response_model=api.PrivacyPreferenceResponse)
async def put_privacy_preferences(
    body: PrivacyPreferenceIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(UserSettings, user.id)
    if row is None:
        row = UserSettings(user_id=user.id, privacy_blur=body.privacy_blur)
        db.add(row)
    else:
        row.privacy_blur = body.privacy_blur
    await db.commit()
    return {"privacy_blur": row.privacy_blur}


@app.put("/budget", response_model=api.BudgetResponse)
async def put_budget(
    body: BudgetIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    effective_from = as_utc(body.effective_from) or now_utc()
    if effective_from > now_utc() + timedelta(days=366):
        raise HTTPException(422, "Budget effective date is too far in the future")
    row = Budget(
        user_id=user.id,
        monthly_limit_minor=body.monthly_limit_minor,
        effective_from=effective_from,
    )
    db.add(row)
    await db.commit()
    return {"monthly_limit_minor": row.monthly_limit_minor, "effective_from": row.effective_from}


@app.get("/budget/velocity", response_model=api.BudgetVelocityResponse)
async def budget_velocity(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    budget = (
        await db.execute(
            select(Budget)
            .where(Budget.user_id == user.id, Budget.effective_from <= now_utc())
            .order_by(Budget.effective_from.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if budget is None:
        raise HTTPException(404, "Monthly budget not set")
    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    spent = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
                Transaction.account_id.in_(active_accounts(user.id, now)),
                Transaction.direction == Direction.debit,
                Transaction.posted_at >= month_start,
                Transaction.account_id.in_(select(Account.id).where(Account.currency == "NGN")),
                Transaction.posted_at <= now,
            )
        )
    ).scalar_one()
    projected = projected_month_end_spend(spent, now)
    percentage = round(spent * 100 / budget.monthly_limit_minor, 2)
    status = (
        "exceeded"
        if spent > budget.monthly_limit_minor
        else ("warning" if projected > budget.monthly_limit_minor else "on_track")
    )
    return {
        "spent_minor": spent,
        "monthly_limit_minor": budget.monthly_limit_minor,
        "percentage": percentage,
        "projected_month_end_minor": projected,
        "status": status,
        "as_of": now,
    }


def obligation_response(row: Obligation) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "lender_name": row.lender_name,
        "kind": row.kind,
        "amount_minor": row.amount_minor,
        "cadence_days": row.cadence_days,
        "next_due_date": row.next_due_date,
        "days_until_due": (row.next_due_date - now_utc().date()).days,
        "confidence_bps": row.confidence_bps,
        "status": row.status,
        "source": row.source,
        "due_date_estimated": row.source == "detected",
    }


@app.post("/obligations", status_code=201, response_model=api.ObligationResponse)
async def create_obligation(
    body: ObligationIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if body.account_id is not None:
        account = (
            await db.execute(
                select(Account).where(Account.id == body.account_id, Account.user_id == user.id)
            )
        ).scalar_one_or_none()
        if account is None:
            raise HTTPException(404, "Account not found")
    row = Obligation(
        user_id=user.id,
        account_id=body.account_id,
        lender_name=body.lender_name,
        kind=body.kind,
        amount_minor=body.amount_minor,
        cadence_days=body.cadence_days,
        next_due_date=body.next_due_date,
        confidence_bps=10_000,
        status="upcoming",
        source="manual",
    )
    db.add(row)
    await db.commit()
    return obligation_response(row)


@app.get("/obligations", response_model=list[api.ObligationResponse])
async def list_obligations(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Obligation)
            .where(Obligation.user_id == user.id, Obligation.status != "dismissed")
            .order_by(Obligation.next_due_date.asc())
        )
    ).scalars()
    return [obligation_response(row) for row in rows]


@app.get("/obligations/{obligation_id}", response_model=api.ObligationDetailResponse)
async def obligation_detail(
    obligation_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = (
        await db.execute(
            select(Obligation).where(Obligation.id == obligation_id, Obligation.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Obligation not found")
    payments = (
        await db.execute(
            select(ObligationPayment)
            .where(ObligationPayment.obligation_id == row.id)
            .order_by(ObligationPayment.paid_at.desc())
        )
    ).scalars()
    return {
        **obligation_response(row),
        "payments": [
            {
                "transaction_id": item.transaction_id,
                "paid_at": item.paid_at,
                "amount_minor": item.amount_minor,
            }
            for item in payments
        ],
    }


@app.patch("/obligations/{obligation_id}", response_model=api.ObligationResponse)
async def update_obligation(
    obligation_id: UUID,
    body: ObligationUpdateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(Obligation).where(Obligation.id == obligation_id, Obligation.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Obligation not found")
    if body.account_id is not None:
        account = await db.scalar(
            select(Account).where(Account.id == body.account_id, Account.user_id == user.id)
        )
        if account is None:
            raise HTTPException(404, "Account not found")
    for name, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, name, value)
    await db.commit()
    return obligation_response(row)


@app.post("/devices", status_code=201)
async def register_device(
    body: DeviceIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    digest = hash_field(body.token)
    row = (
        await db.execute(select(DeviceToken).where(DeviceToken.token_hash == digest))
    ).scalar_one_or_none()
    if row and row.user_id != user.id:
        raise HTTPException(409, "Device is registered to another user")
    if row is None:
        row = DeviceToken(
            user_id=user.id,
            token_hash=digest,
            token_encrypted=encrypt_field(body.token),
            platform=body.platform,
            last_seen_at=now_utc(),
        )
        db.add(row)
    else:
        row.token_encrypted = encrypt_field(body.token)
        row.platform = body.platform
        row.last_seen_at = now_utc()
        row.is_valid = True
        row.invalidated_at = None
    await db.commit()
    return {"id": row.id, "platform": row.platform, "last_seen_at": row.last_seen_at}


@app.delete("/devices/{device_id}", status_code=204)
async def unregister_device(
    device_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        delete(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.user_id == user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Device not found")
    await db.commit()


def preference_response(row: NotificationPreference | None) -> dict:
    return {
        "overspending_alerts": row.overspending_alerts if row else True,
        "loan_repayment_reminders": row.loan_repayment_reminders if row else True,
        "investment_update_prompts": row.investment_update_prompts if row else True,
    }


@app.get("/notification-preferences")
async def get_notification_preferences(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return preference_response(await db.get(NotificationPreference, user.id))


@app.put("/notification-preferences")
async def put_notification_preferences(
    body: NotificationPreferencesIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(NotificationPreference, user.id)
    if row is None:
        row = NotificationPreference(user_id=user.id)
        db.add(row)
    row.overspending_alerts = body.overspending_alerts
    row.loan_repayment_reminders = body.loan_repayment_reminders
    row.investment_update_prompts = body.investment_update_prompts
    await db.commit()
    return preference_response(row)


@app.post("/statements/upload")
async def upload_statement(
    account_id: UUID,
    file: Annotated[UploadFile, File()],
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in {
        "text/csv", "application/vnd.ms-excel", "application/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/pdf",
    }:
        raise HTTPException(415, "PDF, CSV or XLSX required")
    data = await file.read(2_000_001)
    try:
        rows = StatementUploadProvider().parse(data, file.filename or "statement.csv")
    except (ProviderError, ValueError):
        # Keep parse failures generic so CSV cell contents cannot leak into errors.
        raise HTTPException(422, "Invalid statement") from None
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
    await sync_detected_obligations(db, user.id)
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
    payload = x.payload_json
    value_minor = next(
        (
            payload[key]
            for key in (
                "amount_minor",
                "annualised_minor",
                "delta_minor",
                "overshoot_minor",
                "outflow_minor",
            )
            if isinstance(payload.get(key), int)
        ),
        None,
    )
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
        "payload": payload,
        "number_minor": value_minor,
        "why_it_matters": payload.get("why_it_matters"),
        "action": payload.get("action"),
        "confidence_bps": payload.get("confidence_bps"),
        "confidence_label": payload.get("confidence_label"),
        "evidence_transaction_ids": payload.get("transaction_ids", []),
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
        "/onboarding/": "Onboarding",
        "/identity/": "Identity",
        "/assets": "Assets",
        "/net-position": "Assets",
        "/category-rules": "Category rules",
        "/analytics/": "Analytics",
        "/budget": "Budget",
        "/obligations": "Obligations",
        "/privacy-preferences": "Consents",
        "/devices": "Notifications",
        "/notification-preferences": "Notifications",
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
    error_schema = api.ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = error_schema.pop("$defs", {})
    schema.setdefault("components", {}).setdefault("schemas", {}).update(definitions)
    schema["components"]["schemas"]["ErrorResponse"] = error_schema
    schema["components"]["securitySchemes"]["HTTPBearer"]["description"] = (
        "App-issued JWT after OTP verification. Refresh tokens rotate on every use; "
        "refresh-token replay revokes that family. Logout-all revokes access sessions."
    )
    seen: set[str] = set()
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            _document_operation(path, method, operation)
            operation.setdefault("security", [])
            documentation = DEMO_OPERATIONS.get((method, path))
            if documentation:
                summary, description, errors = documentation
                operation["summary"] = summary
                operation["description"] = description + (
                    " Requires the signed-in user's Bearer token; resources are owner-scoped."
                    if operation["security"]
                    else ""
                )
                for code in (*errors, 500):
                    operation["responses"][str(code)] = {
                        "description": ERROR_MESSAGES[code],
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                                "example": {"detail": ERROR_MESSAGES[code]},
                            }
                        },
                    }
                if path == "/accounts/{account_id}/refresh":
                    operation["responses"]["429"]["headers"] = {
                        "Retry-After": {
                            "description": "Seconds remaining in the refresh cooldown.",
                            "schema": {"type": "integer", "minimum": 1},
                        }
                    }
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
