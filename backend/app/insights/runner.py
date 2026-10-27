"""Persist the output of pure detectors for a consent-filtered user ledger."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client_factory import client_for
from app.ai.explain import LLMExplanationService
from app.insights.registry import run_all
from app.ledger.service import ledger_view
from app.models import InsightRecord, UserSettings


async def run_for_user(db: AsyncSession, user_id: UUID, now: datetime) -> int:
    """Run all detectors and upsert by user and period-aware dedupe key."""
    view, settings = await ledger_view(db, user_id, now)
    source_account_ids = sorted(balance.account_id for balance in view.balances)
    explainer = LLMExplanationService(client_for())
    user_settings = await db.get(UserSettings, user_id)
    count = 0
    for found in run_all(view, settings, now):
        key = f"{found.dedupe_key}:{now.year}-{now.month:02d}"
        existing = (
            await db.execute(
                select(InsightRecord).where(
                    InsightRecord.user_id == user_id, InsightRecord.dedupe_key == key
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        payload = {**found.payload, "source_account_ids": source_account_ids}
        row = InsightRecord(
            user_id=user_id,
            module=found.module,
            kind=found.kind,
            severity=found.severity,
            title="",
            body="",
            payload_json=payload,
            dedupe_key=key,
            created_at=now,
            dismissed_at=None,
        )
        title, body, source, prompt, cache_key = await explainer.explain(
            db, row, user_settings, now
        )
        row.title, row.body = title, body
        row.wording_source = source
        row.prompt_version = prompt
        row.wording_cache_key = cache_key
        db.add(row)
        count += 1
    return count
