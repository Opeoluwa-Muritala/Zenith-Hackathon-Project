"""Optional LLM phrasing for detector facts with strict template fallback."""

import asyncio
import hashlib
import json
import logging
import time

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audit import record
from app.ai.budget import budget_allowed
from app.ai.client import LLMClient
from app.ai.prompts import INSIGHT_PROMPT_VERSION, INSIGHT_SYSTEM, facts_message
from app.ai.redaction import insight_input
from app.ai.verify import valid_output
from app.core.config import get_settings
from app.explain.service import WEALTH_FOOTER, TemplateExplanationService
from app.models import InsightRecord, UserSettings

logger = logging.getLogger("cashlens.ai.explain")


class InsightCopy(BaseModel):
    """Bounded model copy validated before it reaches durable storage."""

    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(max_length=60)
    body: str = Field(max_length=280)


class LLMExplanationService:
    """Phrase an insight only when global and user opt-in and budgets allow."""

    def __init__(self, client: LLMClient | None):
        self.client = client
        self.templates = TemplateExplanationService()

    async def explain(
        self,
        db: AsyncSession,
        row: InsightRecord,
        user_settings: UserSettings | None,
        now,
    ) -> tuple[str, str, str, str | None, str | None]:
        """Return title/body/source/prompt/cache fields, falling back on every failure."""
        title, body = self.templates.explain(row.kind, row.payload_json)
        row.template_title, row.template_body = title, body
        config = get_settings()
        fallback = (title, body, "template", None, None)
        if (
            not config.ai_enabled_global
            or not user_settings
            or not user_settings.ai_enabled
            or self.client is None
            or not await budget_allowed(db, row.user_id, now)
        ):
            return fallback
        safe = insight_input(row.kind, row.module, row.payload_json, title, body)
        encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"))
        cache_key = hashlib.sha256((INSIGHT_PROMPT_VERSION + encoded).encode()).hexdigest()
        cached = (
            await db.execute(
                select(InsightRecord).where(
                    InsightRecord.user_id == row.user_id,
                    InsightRecord.wording_cache_key == cache_key,
                    InsightRecord.wording_source == "ai",
                )
            )
        ).scalar_one_or_none()
        if cached:
            return cached.title, cached.body, "ai", INSIGHT_PROMPT_VERSION, cache_key
        started = time.monotonic()
        tokens_in = tokens_out = 0
        verified = False
        try:
            result = await asyncio.wait_for(
                self.client.complete(
                    model=config.ai_explain_model,
                    system=INSIGHT_SYSTEM,
                    messages=[{"role": "user", "content": facts_message(safe)}],
                    tools=[],
                    max_tokens=config.ai_max_tokens_explain,
                    temperature=0.2,
                ),
                timeout=config.ai_request_timeout_s,
            )
            tokens_in, tokens_out = result.input_tokens, result.output_tokens
            try:
                parsed = InsightCopy.model_validate_json(result.text)
            except (ValidationError, ValueError):
                repair = await asyncio.wait_for(
                    self.client.complete(
                        model=config.ai_explain_model,
                        system=INSIGHT_SYSTEM,
                        messages=[
                            {"role": "user", "content": facts_message(safe)},
                            {"role": "assistant", "content": result.text[:1000]},
                            {
                                "role": "user",
                                "content": (
                                    "Repair the prior output as valid JSON with only title and "
                                    "body strings. Use the same verified data."
                                ),
                            },
                        ],
                        tools=[],
                        max_tokens=config.ai_max_tokens_explain,
                        temperature=0.2,
                    ),
                    timeout=config.ai_request_timeout_s,
                )
                tokens_in += repair.input_tokens
                tokens_out += repair.output_tokens
                result = repair
                parsed = InsightCopy.model_validate_json(result.text)
            verified = valid_output(parsed.title + " " + parsed.body, safe, max_length=400)
            if verified:
                if row.module == "wealth" and WEALTH_FOOTER not in parsed.body:
                    prefix = parsed.body.rstrip()[: 279 - len(WEALTH_FOOTER)]
                    parsed.body = f"{prefix} {WEALTH_FOOTER}".strip()
                await record(
                    db,
                    user_id=row.user_id,
                    feature="explain",
                    model=result.model or config.ai_explain_model,
                    prompt_version=INSIGHT_PROMPT_VERSION,
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    verification_passed=True,
                    fallback_used=False,
                    tools_used=[],
                    now=now,
                )
                return parsed.title, parsed.body, "ai", INSIGHT_PROMPT_VERSION, cache_key
        except (RuntimeError, ValidationError, ValueError, TypeError, TimeoutError):
            logger.info("ai_explanation_fallback", extra={"kind": row.kind})
        await record(
            db,
            user_id=row.user_id,
            feature="explain",
            model=config.ai_explain_model,
            prompt_version=INSIGHT_PROMPT_VERSION,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_ms=int((time.monotonic() - started) * 1000),
            verification_passed=verified,
            fallback_used=True,
            tools_used=[],
            now=now,
        )
        return fallback
