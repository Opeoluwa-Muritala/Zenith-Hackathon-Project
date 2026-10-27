import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Direction(enum.StrEnum):
    credit = "credit"
    debit = "debit"


class AccountType(enum.StrEnum):
    current = "current"
    savings = "savings"
    wallet = "wallet"


class Channel(enum.StrEnum):
    NIP = "NIP"
    POS = "POS"
    USSD = "USSD"
    WEB = "WEB"
    ATM = "ATM"
    OTHER = "OTHER"


class SeriesStatus(enum.StrEnum):
    active = "active"
    lapsed = "lapsed"
    cancelled = "cancelled"


class AccountCategory(enum.StrEnum):
    commercial_bank = "commercial_bank"
    digital_bank_wallet = "digital_bank_wallet"
    investment = "investment"
    loan_credit = "loan_credit"


class SyncStatus(enum.StrEnum):
    ok = "ok"
    delayed = "delayed"
    error = "error"


class DiscoveredAccountStatus(enum.StrEnum):
    discovered = "discovered"
    linked = "linked"
    skipped = "skipped"


class ManualAssetPlatform(enum.StrEnum):
    risevest = "risevest"
    cowrywise = "cowrywise"
    bamboo = "bamboo"
    chaka = "chaka"
    real_estate = "real_estate"
    custom_cash_vault = "custom_cash_vault"


class ManualAssetCategory(enum.StrEnum):
    mutual_funds = "mutual_funds"
    us_equities = "us_equities"
    real_estate = "real_estate"
    dollar_savings = "dollar_savings"
    eurobonds = "eurobonds"


class UpdateCadence(enum.StrEnum):
    biweekly = "biweekly"
    monthly = "monthly"


class CategorySource(enum.StrEnum):
    auto = "auto"
    user_rule = "user_rule"
    manual = "manual"


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    bvn_hash: Mapped[str | None] = mapped_column(String(64))
    bvn_last4: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sessions_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    identifier: Mapped[str] = mapped_column(String(254), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    salt: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthLockout(Base):
    __tablename__ = "auth_lockouts"
    identifier_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    event: Mapped[str] = mapped_column(String(50), index=True)
    subject_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProviderCallLog(Base):
    __tablename__ = "provider_call_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    operation: Mapped[str] = mapped_column(String(60))
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    outcome: Mapped[str] = mapped_column(String(20))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    family_id: Mapped[UUID] = mapped_column(index=True, default=uuid4)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(100))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentAudit(Base):
    __tablename__ = "consent_audit"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    consent_id: Mapped[UUID] = mapped_column(ForeignKey("consents.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(80))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    savings_rate_bps: Mapped[int] = mapped_column(Integer, default=0)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    consent_id: Mapped[UUID] = mapped_column(ForeignKey("consents.id"))
    account_number_masked: Mapped[str] = mapped_column(String(20))
    type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    current_balance_minor: Mapped[int] = mapped_column(BigInteger)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_cursor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category: Mapped[AccountCategory] = mapped_column(
        Enum(AccountCategory), default=AccountCategory.commercial_bank
    )
    available_balance_minor: Mapped[int | None] = mapped_column(BigInteger)
    ledger_balance_minor: Mapped[int | None] = mapped_column(BigInteger)
    balance_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), default=SyncStatus.ok)
    sync_paused: Mapped[bool] = mapped_column(default=False)
    institution: Mapped[Institution] = relationship()


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    canonical_name: Mapped[str] = mapped_column(String(100), unique=True)
    category_default: Mapped[str] = mapped_column(String(40))
    is_subscription_like: Mapped[bool] = mapped_column(default=False)
    legitimately_repeating: Mapped[bool] = mapped_column(default=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("account_id", "dedupe_hash"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[Direction] = mapped_column(Enum(Direction))
    narration_raw: Mapped[str] = mapped_column(Text)
    narration_clean: Mapped[str] = mapped_column(String(200))
    merchant_id: Mapped[UUID | None] = mapped_column(ForeignKey("merchants.id"))
    category: Mapped[str] = mapped_column(String(40))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    balance_after_minor: Mapped[int | None] = mapped_column(BigInteger)
    dedupe_hash: Mapped[str] = mapped_column(String(64))
    decoded_merchant: Mapped[str | None] = mapped_column(String(100))
    category_source: Mapped[CategorySource] = mapped_column(
        Enum(CategorySource), default=CategorySource.auto
    )
    source: Mapped[str] = mapped_column(String(20), default="mono")
    parse_confidence_bps: Mapped[int] = mapped_column(Integer, default=10000)
    classification_method: Mapped[str] = mapped_column(String(20), default="rule")
    merchant: Mapped[Merchant | None] = relationship()


class RecurringSeries(Base):
    __tablename__ = "recurring_series"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"))
    cadence_days: Mapped[int] = mapped_column(Integer)
    typical_amount_minor: Mapped[int] = mapped_column(BigInteger)
    last_amount_minor: Mapped[int] = mapped_column(BigInteger)
    previous_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    cycles: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_expected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[SeriesStatus] = mapped_column(Enum(SeriesStatus))
    direction: Mapped[Direction] = mapped_column(Enum(Direction), default=Direction.debit)
    merchant: Mapped[Merchant] = relationship()


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    safe_buffer_minor: Mapped[int] = mapped_column(BigInteger, default=500000)
    payday_hint: Mapped[int | None] = mapped_column(Integer)
    discretionary_categories: Mapped[list] = mapped_column(JSON, default=list)
    nominal_tbill_rate_bps: Mapped[int] = mapped_column(Integer, default=1500)
    ai_enabled: Mapped[bool] = mapped_column(default=False)


class InsightRecord(Base):
    __tablename__ = "insights"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    template_title: Mapped[str] = mapped_column(String(160), default="")
    template_body: Mapped[str] = mapped_column(Text, default="")
    wording_source: Mapped[str] = mapped_column(String(12), default="template")
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    wording_cache_key: Mapped[str | None] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderLink(Base):
    __tablename__ = "provider_links"
    __table_args__ = (UniqueConstraint("provider", "provider_account_id_hash"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_id: Mapped[UUID] = mapped_column(
        ForeignKey("consents.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_account_id_encrypted: Mapped[str | None] = mapped_column(String(512))
    provider_account_id_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    data_status: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def provider_account_id(self) -> str | None:
        if not self.provider_account_id_encrypted:
            return None
        from app.core.encryption import decrypt_field

        return decrypt_field(self.provider_account_id_encrypted)

    @provider_account_id.setter
    def provider_account_id(self, value: str | None) -> None:
        from app.core.encryption import encrypt_field, hash_field

        self.provider_account_id_encrypted = encrypt_field(value) if value else None
        self.provider_account_id_hash = hash_field(value) if value else None


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_key: Mapped[str] = mapped_column(String(64), unique=True)
    event_name: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_token: Mapped[str | None] = mapped_column(String(36))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content_redacted: Mapped[str] = mapped_column(Text)
    tool_names: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AiAudit(Base):
    __tablename__ = "ai_audit"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    feature: Mapped[str] = mapped_column(String(12))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    verification_passed: Mapped[bool] = mapped_column(default=False)
    fallback_used: Mapped[bool] = mapped_column(default=False)
    tools_used: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DiscoveredAccount(Base):
    __tablename__ = "discovered_accounts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    account_name: Mapped[str] = mapped_column(String(160))
    account_designation: Mapped[str] = mapped_column(String(40))
    bank_code: Mapped[str] = mapped_column(String(10))
    nip_code: Mapped[str | None] = mapped_column(String(10))
    institution_name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(40))
    account_number_encrypted: Mapped[str] = mapped_column(String(512))
    account_number_last4: Mapped[str] = mapped_column(String(4))
    account_number_hash: Mapped[str] = mapped_column(String(64))
    institution_id: Mapped[str | None] = mapped_column(String(80))
    institution_auth_method: Mapped[str | None] = mapped_column(String(40))
    link_ref: Mapped[str | None] = mapped_column(String(80), unique=True)
    account_match_requested: Mapped[bool] = mapped_column(default=False)
    status: Mapped[DiscoveredAccountStatus] = mapped_column(
        Enum(DiscoveredAccountStatus), default=DiscoveredAccountStatus.discovered
    )
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("user_id", "bank_code", "account_number_hash"),)


class ManualAsset(Base):
    __tablename__ = "manual_assets"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[ManualAssetPlatform] = mapped_column(Enum(ManualAssetPlatform))
    category: Mapped[ManualAssetCategory] = mapped_column(Enum(ManualAssetCategory))
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    fx_rate_used: Mapped[int | None] = mapped_column(BigInteger)
    update_cadence: Mapped[UpdateCadence] = mapped_column(Enum(UpdateCadence))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FxRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    rate: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(80))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CategoryRule(Base):
    __tablename__ = "category_rules"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    counterparty_key: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("user_id", "counterparty_key"),)


class ClassificationCorrection(Base):
    __tablename__ = "classification_corrections"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    counterparty_key: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(40))
    confirmed: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    monthly_limit_minor: Mapped[int] = mapped_column(BigInteger)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Obligation(Base):
    __tablename__ = "obligations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    lender_name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    cadence_days: Mapped[int] = mapped_column(Integer)
    next_due_date: Mapped[date] = mapped_column()
    confidence_bps: Mapped[int] = mapped_column(Integer, default=10_000)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    __table_args__ = (UniqueConstraint("user_id", "account_id", "lender_name", "kind", "source"),)


class ObligationPayment(Base):
    __tablename__ = "obligation_payments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    obligation_id: Mapped[UUID] = mapped_column(
        ForeignKey("obligations.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), unique=True
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_minor: Mapped[int] = mapped_column(BigInteger)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_encrypted: Mapped[str] = mapped_column(String(512))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    platform: Mapped[str] = mapped_column(String(20))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    overspending_alerts: Mapped[bool] = mapped_column(default=True)
    loan_repayment_reminders: Mapped[bool] = mapped_column(default=True)
    investment_update_prompts: Mapped[bool] = mapped_column(default=True)


class BvnLookupSession(Base):
    __tablename__ = "bvn_lookup_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mono_session_id: Mapped[str] = mapped_column(String(100), unique=True)
    scope: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="initiated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
