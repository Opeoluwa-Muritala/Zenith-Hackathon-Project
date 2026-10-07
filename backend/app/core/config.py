from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PRODUCT_NAME = "cashlens"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env", "app/.env"), extra="ignore")
    database_url: str = "postgresql+asyncpg://cashlens:cashlens_dev@localhost:5432/cashlens"
    jwt_secret: str = Field("development-only-secret-change-me-32bytes", min_length=32)
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    dev_otp: str = "123456"
    access_minutes: int = 15
    refresh_days: int = 30
    jwt_issuer: str = "cashlens-api"
    jwt_audience: str = "cashlens-mobile"
    bvn_pepper: str = "development-bvn-pepper-change-me"
    aggregator_provider: str = "mock"
    mono_base_url: str = "https://api.withmono.com"
    mono_secret_key: str = ""
    mono_public_key: str = ""
    webhook_secure_key: str = ""
    mono_redirect_url: str = "cashlens://mono/callback"
    ai_enabled_global: bool = False
    ai_provider: str = "groq"
    groq_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_explain_model: str = "llama-3.1-8b-instant"
    ai_chat_model: str = "llama-3.3-70b-versatile"
    ai_max_tokens_explain: int = 240
    ai_max_tokens_chat: int = 700
    ai_daily_token_budget_per_user: int = 12_000
    ai_global_daily_token_budget: int = 250_000
    ai_request_timeout_s: float = 20.0
    ai_chat_requests_per_minute: int = 10
    assistant_retention_days: int = 30

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
        if self.environment != "production":
            return
        if self.jwt_secret == "development-only-secret-change-me-32bytes":
            raise RuntimeError("JWT_SECRET must be configured in production")
        if self.bvn_pepper == "development-bvn-pepper-change-me":
            raise RuntimeError("BVN_PEPPER must be configured in production")
        if self.dev_otp:
            raise RuntimeError("DEV_OTP must be disabled in production")
        if "*" in self.origins:
            raise RuntimeError("Wildcard CORS is forbidden in production")
        if self.aggregator_provider == "mono" and not self.mono_secret_key:
            raise RuntimeError("MONO_SECRET_KEY is required for Mono")
        if (
            self.ai_enabled_global
            and self.ai_provider == "groq"
            and not self.groq_key
        ):
            raise RuntimeError("GROQ_KEY is required when AI is enabled")

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
