"""Persist the output of pure detectors for a consent-filtered user ledger."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.explain.service import TemplateExplanationService
from app.insights.registry import run_all
from app.ledger.service import ledger_view
from app.models import InsightRecord


async def run_for_user(db: AsyncSession, user_id: UUID, now: datetime) -> int:
    """Run all detectors and upsert by user and period-aware dedupe key."""
    view, settings = await ledger_view(db, user_id, now)
    source_account_ids = sorted(balance.account_id for balance in view.balances)
    explainer = TemplateExplanationService()
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
        title, body = explainer.explain(found.kind, found.payload)
        payload = {**found.payload, "source_account_ids": source_account_ids}
        db.add(
            InsightRecord(
                user_id=user_id,
                module=found.module,
                kind=found.kind,
                severity=found.severity,
                title=title,
                body=body,
                payload_json=payload,
                dedupe_key=key,
                created_at=now,
                dismissed_at=None,
            )
        )
        count += 1
    return count
