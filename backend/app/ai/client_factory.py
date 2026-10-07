"""Select and cache the configured provider; CI's fake mode has no network client."""

from functools import lru_cache

from app.ai.client import FakeLLMClient, GroqClient, LLMClient
from app.core.config import get_settings


@lru_cache(maxsize=1)
def client_for() -> LLMClient | None:
    """Return no client when globally disabled or a cached configured provider."""
    config = get_settings()
    if not config.ai_enabled_global:
        return None
    if config.ai_provider == "fake":
        return FakeLLMClient()
    if config.ai_provider == "groq":
        return GroqClient(
            config.groq_key,
            config.groq_base_url,
            timeout_s=config.ai_request_timeout_s,
        )
    return None
