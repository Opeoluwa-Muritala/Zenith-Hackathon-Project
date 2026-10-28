from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PRODUCT_NAME = "Fetch"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env", "app/.env"), extra="ignore", populate_by_name=True
    )
    database_url: str = "postgresql+asyncpg://localhost/fetch"
    jwt_secret: str = ""
    environment: str = Field("development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))
    redis_url: str = ""
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"
    api_docs_enabled: bool = False
    otp_secret: str = ""
    otp_sender: str = "disabled"
    otp_dev_inbox_enabled: bool = False
    demo_mode: bool = False
    demo_otp_inbox_password: str = Field("", repr=False)
    demo_identifiers: str = ""
    otp_http_url: str = ""
    otp_http_key: str = ""
    otp_sender_id: str = ""
    otp_expiry_seconds: int = Field(300, ge=60, le=900)
    otp_max_attempts: int = Field(5, ge=1, le=10)
    otp_resend_cooldown_seconds: int = Field(60, ge=1, le=600)
    otp_lockout_threshold: int = Field(5, ge=2, le=20)
    otp_lockout_base_seconds: int = Field(60, ge=10, le=3600)
    balance_stale_minutes: int = Field(45, ge=1, le=1440)
    account_refresh_cooldown_seconds: int = Field(3600, ge=60, le=86400)
    mono_refresh_monthly_limit: int = Field(2, ge=0, le=100)
    fx_provider_name: str = ""
    fx_provider_url: str = ""
    fx_provider_key: str = ""
    fx_ttl_hours: int = Field(6, ge=1, le=168)
    access_minutes: int = 15
    refresh_days: int = 30
    live_sync_trial_days: int = Field(14, ge=1, le=90)
    free_live_account_limit: int = Field(2, ge=1, le=2)
    jwt_issuer: str = "fetch-api"
    jwt_audience: str = "fetch-mobile"
    bvn_pepper: str = ""
    aggregator_provider: str = "mock"
    mono_base_url: str = "https://api.withmono.com"
    mono_secret_key: str = ""
    mono_lookup_secret_key: str = ""
    mono_public_key: str = ""
    webhook_secure_key: str = ""
    mono_redirect_url: str = "fetch://mono/callback"
    mono_account_match_enabled: bool = False
    ai_enabled_global: bool = False
    ai_provider: str = "groq"
    groq_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_explain_model: str = "openai/gpt-oss-20b"
    ai_chat_model: str = "openai/gpt-oss-120b"
    ai_max_tokens_explain: int = 240
    ai_max_tokens_chat: int = 700
    ai_daily_token_budget_per_user: int = 12_000
    ai_global_daily_token_budget: int = 250_000
    ai_request_timeout_s: float = 20.0
    ai_chat_requests_per_minute: int = 10
    assistant_retention_days: int = 30
    fcm_credentials_json: str = Field("", repr=False)
    field_encryption_key: str = ""
    field_encryption_key_id: str = "primary"
    field_encryption_previous_keys: str = "{}"

    @property
    def async_database_url(self) -> str:
        """Translate hosted PostgreSQL URLs for asyncpg without exposing credentials."""
        url = make_url(self.database_url)
        if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
            raise ValueError("DATABASE_URL must use PostgreSQL")
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        if sslmode and sslmode != "disable":
            query["ssl"] = sslmode
        return url.set(drivername="postgresql+asyncpg", query=query).render_as_string(
            hide_password=False
        )

    def validate_runtime(self) -> None:
        if self.demo_mode:
            if self.environment == "production":
                raise RuntimeError("Demo mode is forbidden in production")
            if len(self.demo_otp_inbox_password) < 16 or not self.demo_identity_allowlist:
                raise RuntimeError("Demo inbox requires a password and allowlisted identifiers")
            if (
                len(self.jwt_secret) < 32
                or len(self.otp_secret) < 32
                or not self.stable_field_encryption_available
            ):
                raise RuntimeError("Demo mode requires JWT, OTP and field encryption secrets")
            if self.otp_sender != "dev_inbox" or not self.otp_dev_inbox_enabled:
                raise RuntimeError("Demo mode requires the explicitly enabled development inbox")
        if self.demo_mode or self.environment == "production":
            if any(
                value.startswith("REPLACE_")
                for value in (self.jwt_secret, self.otp_secret, self.bvn_pepper)
            ):
                raise RuntimeError("Replace secret placeholders before startup")
            if self.field_encryption_key:
                try:
                    Fernet(self.field_encryption_key.encode())
                except (ValueError, TypeError):
                    raise RuntimeError("A valid FIELD_ENCRYPTION_KEY is required") from None
        if self.environment != "production":
            return
        if (
            len(self.jwt_secret) < 32
            or self.jwt_secret == "development-only-secret-change-me-32bytes"
        ):
            raise RuntimeError("JWT_SECRET must be configured in production")
        if len(self.bvn_pepper) < 32 or self.bvn_pepper == "development-bvn-pepper-change-me":
            raise RuntimeError("BVN_PEPPER must be configured in production")
        if len(self.otp_secret) < 32:
            raise RuntimeError("OTP_SECRET must be configured in production")
        if self.otp_sender != "http" or self.otp_dev_inbox_enabled:
            raise RuntimeError("A production HTTP OTP sender is required")
        if not self.otp_http_url.startswith("https://") or not self.otp_http_key:
            raise RuntimeError("HTTPS OTP sender URL and key are required")
        if "*" in self.origins:
            raise RuntimeError("Wildcard CORS is forbidden in production")
        if self.aggregator_provider == "mono" and not self.mono_secret_key:
            raise RuntimeError("MONO_SECRET_KEY is required for Mono")
        if not self.mono_lookup_secret_key:
            raise RuntimeError("MONO_LOOKUP_SECRET_KEY is required in production")
        if not self.field_encryption_key:
            raise RuntimeError("FIELD_ENCRYPTION_KEY is required in production")
        database = make_url(self.database_url)
        if database.host in {None, "localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Production DATABASE_URL must not use a development host")
        if database.username in {None, "postgres", "user"} or database.database in {
            None,
            "fetch",
            "postgres",
            "dbname",
        }:
            raise RuntimeError("Production DATABASE_URL uses development credentials")
        if self.fx_provider_url and (
            not self.fx_provider_url.startswith("https://") or not self.fx_provider_name
        ):
            raise RuntimeError("Production FX provider requires a name and HTTPS URL")
        if self.ai_enabled_global and self.ai_provider == "groq" and not self.groq_key:
            raise RuntimeError("GROQ_KEY is required when AI is enabled")

    @property
    def demo_identity_allowlist(self) -> set[str]:
        return {item.strip().lower() for item in self.demo_identifiers.split(",") if item.strip()}

    @property
    def stable_field_encryption_available(self) -> bool:
        return bool(self.field_encryption_key) or (
            len(self.mono_secret_key) >= 24 and not self.mono_secret_key.startswith("REPLACE_")
        )

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
