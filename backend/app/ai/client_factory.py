"""Select and cache the configured provider; CI's fake mode has no network client."""

from functools import lru_cache

from app.ai.client import FakeLLMClient, LLMClient, OpenRouterClient
from app.core.config import get_settings


@lru_cache(maxsize=1)
def client_for() -> LLMClient | None:
    """Return no client when globally disabled or a cached configured provider."""
    config = get_settings()
    if not config.ai_enabled_global:
        return None
    if config.ai_provider == "fake":
        return FakeLLMClient()
    if config.ai_provider == "openrouter":
        fallbacks = tuple(
            item.strip() for item in config.ai_fallback_models.split(",") if item.strip()
        )
        return OpenRouterClient(
            config.openrouter_api_key,
            config.openrouter_base_url,
            timeout_s=config.ai_request_timeout_s,
            data_collection=config.ai_data_collection,
            require_zdr=config.ai_require_zdr,
            site_url=config.ai_site_url,
            site_name=config.ai_site_name,
            fallback_models=fallbacks,
        )
    return None
