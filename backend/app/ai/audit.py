"""Write metadata-only audit records and log no prompts, outputs or tool facts."""

import hashlib
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiAudit

logger = logging.getLogger("cashlens.ai")


async def record(
    db: AsyncSession,
    *,
    user_id: UUID,
    feature: str,
    model: str,
    prompt_version: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    verification_passed: bool,
    fallback_used: bool,
    tools_used: list[str],
    now: datetime,
) -> None:
    """Persist usage metadata and emit a PII-safe metadata-only log event."""
    hashed_user = hashlib.sha256(user_id.bytes).hexdigest()[:16]
    db.add(
        AiAudit(
            user_id=user_id,
            feature=feature,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            verification_passed=verification_passed,
            fallback_used=fallback_used,
            tools_used=tools_used,
            created_at=now,
        )
    )
    logger.info(
        "ai_request",
        extra={
            "feature": feature,
            "model": model,
            "user_hash": hashed_user,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "verification_passed": verification_passed,
            "fallback_used": fallback_used,
            "tools_used": tools_used,
        },
    )
