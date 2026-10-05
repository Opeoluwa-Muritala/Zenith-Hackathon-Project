from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCT_NAME = "cashlens"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")
    database_url: str = "postgresql+asyncpg://cashlens:cashlens_dev@localhost:5432/cashlens"
    jwt_secret: str = Field("development-only-secret-change-me-32bytes", min_length=32)
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    dev_otp: str = "123456"
    access_minutes: int = 15
    refresh_days: int = 30

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
