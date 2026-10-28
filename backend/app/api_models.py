"""Public response contracts for the mobile demo, with currency and time conventions."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    AccountCategory,
    AccountType,
    CategorySource,
    Direction,
    ManualAssetCategory,
    ManualAssetPlatform,
    UpdateCadence,
)

Money = Annotated[
    int,
    Field(
        description="Integer minor units: NGN kobo or USD cents, as identified by currency.",
        examples=[10000],
    ),
]
NgnMoney = Annotated[int, Field(description="Integer NGN minor units (kobo).", examples=[10000])]
Timestamp = Annotated[
    datetime, Field(description="UTC ISO 8601 timestamp.", examples=["2026-10-14T12:00:00Z"])
]
ResourceID = Annotated[
    UUID,
    Field(
        description="Application resource identifier.",
        examples=["00000000-0000-4000-8000-000000000001"],
    ),
]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        for name, field in cls.model_fields.items():
            if not field.description:
                field.description = name.replace("_", " ").capitalize() + "."
        cls.model_rebuild(force=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_timestamps(cls, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value


class ValidationIssue(ApiModel):
    loc: list[str | int]
    type: str
    msg: str


class ErrorResponse(ApiModel):
    detail: str | list[ValidationIssue]


class HealthResponse(ApiModel):
    status: Literal["ok"]
    product: str


class StatusResponse(ApiModel):
    status: str


class TokenResponse(ApiModel):
    access_token: str = Field(
        description="Short-lived app JWT; send in Authorization: Bearer.",
        examples=["<access-token>"],
    )
    refresh_token: str = Field(
        description="Single-use refresh token; rotation returns a replacement.",
        examples=["<refresh-token>"],
    )
    token_type: Literal["bearer"]


class OtpMethod(ApiModel):
    method: str | None
    hint: str | None


class LookupStartResponse(ApiModel):
    session_id: str
    methods: list[OtpMethod]


class DiscoveredAccountResponse(ApiModel):
    id: ResourceID
    account_name: str
    account_designation: str
    bank_code: str
    nip_code: str | None
    institution_name: str
    account_type: str
    account_number_last4: str = Field(
        max_length=4,
        description="Only the last four digits; never the full account number.",
        examples=["0000"],
    )
    status: Literal["discovered", "linked", "skipped"]


class SelectionResponse(ApiModel):
    selected: int
    skipped: int


class SkippedAccountResponse(ApiModel):
    id: ResourceID
    institution_name: str
    account_type: str
    account_number_last4: str


class HostedLinkResponse(ApiModel):
    ref: ResourceID
    mono_url: str
    institution_mapped: bool


class InitiateLinkResponse(ApiModel):
    ref: ResourceID
    url: str
    status: str


class LinkStatusResponse(ApiModel):
    ref: ResourceID
    status: str
    data_status: str | None
    account_id: ResourceID | None


class ExchangeLinkResponse(ApiModel):
    ref: ResourceID
    status: str


class MockLinkResponse(ApiModel):
    id: ResourceID
    status: str


class ConsentCreatedResponse(ApiModel):
    id: ResourceID
    institution: str
    scope: str = Field(
        description="Scope stored at consent creation, not provider permission badges."
    )


class ConsentResponse(ConsentCreatedResponse):
    revoked_at: Timestamp | None


class BalanceStateResponse(ApiModel):
    balance_minor: Money
    balance_synced_at: Timestamp | None
    cache_age_minutes: int | None
    sync_status: Literal["ok", "delayed"]
    sync_message: str


class AccountListEntry(BalanceStateResponse):
    id: ResourceID
    institution: str
    type: AccountType
    currency: str
    account_number_masked: str
    category_unmapped: bool
    available_balance_minor: Money | None
    ledger_balance_minor: Money | None
    sync_paused: bool
    data_status: str | None


class AccountGroupResponse(ApiModel):
    count: int
    totals_minor_by_currency: dict[str, Money]
    accounts: list[AccountListEntry]


class AccountsResponse(ApiModel):
    groups: dict[AccountCategory, AccountGroupResponse]


class AccountDetailResponse(BalanceStateResponse):
    id: ResourceID
    account_number_masked: str
    type: AccountType
    category: AccountCategory
    category_unmapped: bool
    currency: str
    available_balance_minor: Money | None
    ledger_balance_minor: Money | None
    sync_paused: bool
    data_status: str | None


class RefreshResponse(BalanceStateResponse):
    status: Literal["requested", "synced", "delayed", "cached"]
    job_status: Literal["processing", "finished", "failed"] | None = None
    cached_balance_minor: Money | None = None
    transactions_imported: int | None = None


class PauseResponse(ApiModel):
    sync_paused: bool


class UnlinkResponse(ApiModel):
    status: Literal["pending_unlink", "unlinked"]
    local_data_purged: bool


class SyncResponse(ApiModel):
    accounts_synced: int
    transactions_imported: int


class ManualAssetResponse(ApiModel):
    id: ResourceID
    platform: ManualAssetPlatform
    category: ManualAssetCategory
    currency: Literal["NGN", "USD"]
    amount_minor: Money
    fx_rate_used_ppm: int | None = Field(
        description="Stored NGN per USD rate multiplied by 1,000,000; NGN writes use 1,000,000."
    )
    value_ngn_minor: NgnMoney
    update_cadence: UpdateCadence
    last_updated_at: Timestamp | None
    next_reminder_at: Timestamp | None


class NetPositionResponse(ApiModel):
    cash_minor: NgnMoney
    investments_minor: NgnMoney
    total_minor: NgnMoney
    currency: Literal["NGN"]
    as_of: Timestamp
    fx_rate_warning: bool


class TransactionResponse(ApiModel):
    id: ResourceID
    posted_at: Timestamp
    amount_minor: Money
    direction: Direction
    narration: str
    raw_narration: str = Field(description="Original provider narration, without cleaning.")
    decoded_merchant: str | None
    category: str
    category_source: CategorySource


class RecentTransactionResponse(ApiModel):
    id: ResourceID
    account_id: ResourceID
    account_name: str | None
    masked_number: str
    institution: str
    decoded_merchant: str | None
    amount_minor: Money
    direction: Direction
    category: str
    posted_at: Timestamp


class ReclassificationResponse(ApiModel):
    id: ResourceID
    category: str
    category_source: CategorySource


class CategoryRuleResponse(ApiModel):
    id: ResourceID
    counterparty_key: str
    category: str


class SpendingCategoryResponse(ApiModel):
    category: str
    amount_minor: NgnMoney
    percentage: float


class SpendingResponse(ApiModel):
    period: Literal["this_month", "last_month", "custom"]
    from_date: date = Field(alias="from", description="First included calendar date.")
    to_date: date = Field(alias="to", description="Last included calendar date.")
    total_outflow_minor: NgnMoney
    categories: list[SpendingCategoryResponse]
    own_transfers_excluded: int
    own_transfer_detection: Literal["not_available"]


class BudgetResponse(ApiModel):
    monthly_limit_minor: NgnMoney | None
    effective_from: Timestamp | None


class BudgetVelocityResponse(ApiModel):
    spent_minor: NgnMoney
    monthly_limit_minor: NgnMoney
    percentage: float
    projected_month_end_minor: NgnMoney
    status: Literal["on_track", "warning", "exceeded"]
    as_of: Timestamp


class ObligationResponse(ApiModel):
    id: ResourceID
    account_id: ResourceID | None
    lender_name: str
    kind: Literal["loan", "direct_debit", "subscription"]
    amount_minor: Money
    cadence_days: int
    next_due_date: date
    days_until_due: int
    confidence_bps: int
    status: str
    source: Literal["manual", "detected"]


class ObligationPaymentResponse(ApiModel):
    transaction_id: ResourceID | None
    paid_at: Timestamp
    amount_minor: Money


class ObligationDetailResponse(ObligationResponse):
    payments: list[ObligationPaymentResponse]


class WebhookResponse(ApiModel):
    received: bool
