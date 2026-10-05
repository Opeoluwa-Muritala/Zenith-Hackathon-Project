import enum
from datetime import datetime
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


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    bvn_hash: Mapped[str | None] = mapped_column(String(64))
    bvn_last4: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    payload_json: Mapped[dict] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderLink(Base):
    __tablename__ = "provider_links"
    __table_args__ = (UniqueConstraint("provider", "provider_account_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_id: Mapped[UUID] = mapped_column(
        ForeignKey("consents.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_account_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    data_status: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_key: Mapped[str] = mapped_column(String(64), unique=True)
    event_name: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
