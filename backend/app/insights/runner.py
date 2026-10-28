"""Persist the output of pure detectors for a consent-filtered user ledger."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client_factory import client_for
from app.ai.explain import LLMExplanationService
from app.insights.registry import run_all
from app.ledger.service import ledger_view
from app.models import InsightAlert, InsightRecord, UserSettings

ALERT_KINDS = {
    "leak_finder_headline": (
        "new_leak",
        "A new possible leak was found.",
        "Review the evidence transactions.",
    ),
    "double_charge_price_change": (
        "new_leak",
        "A duplicate or changed charge was found.",
        "Check the charge with the merchant.",
    ),
    "unusual_transfer": (
        "unusual_transfer",
        "An unusual transfer pattern was found.",
        "Confirm that the transfer is expected.",
    ),
    "velocity_warning": (
        "overspending",
        "Projected spending has increased.",
        "Review discretionary spending.",
    ),
    "loan_repayment_due": (
        "loan_repayment_due",
        "A recurring payment is due soon.",
        "Confirm funds are available.",
    ),
}


def _evidence(found, view) -> list[str]:
    explicit = found.payload.get("transaction_ids", [])
    if isinstance(explicit, list) and all(isinstance(item, str) for item in explicit):
        return list(dict.fromkeys(explicit))
    merchant = found.payload.get("merchant")
    return [tx.id for tx in view.transactions if merchant and tx.merchant == merchant]


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
        evidence = _evidence(found, view)
        confidence = min(
            (tx.confidence_bps for tx in view.transactions if tx.id in evidence), default=9000
        )
        payload = {
            **found.payload,
            "transaction_ids": evidence,
            "source_account_ids": source_account_ids,
            "confidence_bps": found.payload.get("confidence_bps", confidence),
            "confidence_label": "low" if confidence < 7000 else "high",
            "why_it_matters": found.payload.get(
                "why_it_matters", "This pattern may affect your available cash."
            ),
            "action": found.payload.get("action", "Review the evidence transactions."),
        }
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
        await db.flush()
        alert = ALERT_KINDS.get(found.kind)
        if alert:
            db.add(
                InsightAlert(
                    user_id=user_id,
                    insight_id=row.id,
                    kind=alert[0],
                    severity=found.severity,
                    what_changed=alert[1],
                    suggested_response=alert[2],
                    created_at=now,
                    read_at=None,
                )
            )
        count += 1
    return count
