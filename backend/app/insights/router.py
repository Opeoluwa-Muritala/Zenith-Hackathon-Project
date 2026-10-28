"""Owner-scoped Phase 5 insight, SME review and alert API."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.db import get_db
from app.core.security import current_user
from app.insights.business import ModeInput, UseReviewInput, label_out, suggest_use
from app.ledger.service import active_accounts
from app.models import (
    InsightAlert,
    InsightProfile,
    InsightRecord,
    Transaction,
    TransactionUseLabel,
    User,
)

router = APIRouter(tags=["Insights"])


@router.put("/insight-profile")
async def set_insight_profile(
    body: ModeInput,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(InsightProfile, user.id)
    if row is None:
        row = InsightProfile(user_id=user.id, mode=body.mode, updated_at=now_utc())
        db.add(row)
    else:
        row.mode, row.updated_at = body.mode, now_utc()
    await db.commit()
    return {"mode": row.mode}


@router.get("/business-personal/review")
async def business_personal_review(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    profile = await db.get(InsightProfile, user.id)
    if profile is None or profile.mode != "sme":
        raise HTTPException(409, "SME mode is required")
    transactions = list(
        (
            await db.scalars(
                select(Transaction)
                .where(Transaction.account_id.in_(active_accounts(user.id, now_utc())))
                .order_by(Transaction.posted_at.desc())
                .limit(500)
            )
        ).all()
    )
    labels = {
        row.transaction_id: row
        for row in (
            await db.scalars(
                select(TransactionUseLabel).where(TransactionUseLabel.user_id == user.id)
            )
        ).all()
    }
    items = []
    totals = {"business": 0, "personal": 0, "unsure": 0}
    for transaction in transactions:
        suggested, confidence = suggest_use(transaction)
        label = labels.get(transaction.id)
        effective = label.confirmed_label if label and label.confirmed_label else suggested
        totals[effective] += transaction.amount_minor
        items.append(
            label_out(
                transaction,
                suggested,
                confidence,
                label.confirmed_label if label else None,
                label.updated_at if label else transaction.posted_at,
            )
        )
    return {"items": items, "split_minor": totals}


@router.put("/business-personal/transactions/{transaction_id}")
async def review_transaction_use(
    transaction_id: UUID,
    body: UseReviewInput,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    transaction = await db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.account_id.in_(active_accounts(user.id, now_utc())),
        )
    )
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    suggested, confidence = suggest_use(transaction)
    row = await db.get(TransactionUseLabel, transaction.id)
    if row is None:
        row = TransactionUseLabel(
            transaction_id=transaction.id,
            user_id=user.id,
            suggested_label=suggested,
            confidence_bps=confidence,
            confirmed_label=body.label,
            updated_at=now_utc(),
        )
        db.add(row)
    elif row.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    else:
        row.confirmed_label, row.updated_at = body.label, now_utc()
    await db.commit()
    return label_out(transaction, suggested, confidence, row.confirmed_label, row.updated_at)


@router.get("/insight-alerts")
async def list_insight_alerts(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["all", "unread"] = "unread",
) -> list[dict]:
    active_ids = {
        str(item) for item in (await db.scalars(active_accounts(user.id, now_utc()))).all()
    }
    query = (
        select(InsightAlert, InsightRecord)
        .join(InsightRecord, InsightAlert.insight_id == InsightRecord.id)
        .where(InsightAlert.user_id == user.id, InsightRecord.user_id == user.id)
    )
    if status == "unread":
        query = query.where(InsightAlert.read_at.is_(None))
    rows = (await db.execute(query.order_by(InsightAlert.created_at.desc()))).all()
    return [
        {
            "id": alert.id,
            "insight_id": alert.insight_id,
            "kind": alert.kind,
            "severity": alert.severity,
            "what_changed": alert.what_changed,
            "suggested_response": alert.suggested_response,
            "created_at": alert.created_at,
            "read_at": alert.read_at,
        }
        for alert, insight in rows
        if set(insight.payload_json.get("source_account_ids", [])) <= active_ids
    ]


@router.post("/insight-alerts/{alert_id}/read")
async def mark_insight_alert_read(
    alert_id: UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    pair = (
        await db.execute(
            select(InsightAlert, InsightRecord)
            .join(InsightRecord, InsightAlert.insight_id == InsightRecord.id)
            .where(
                InsightAlert.id == alert_id,
                InsightAlert.user_id == user.id,
                InsightRecord.user_id == user.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if pair is None:
        raise HTTPException(404, "Alert not found")
    row, insight = pair
    active_ids = {
        str(item) for item in (await db.scalars(active_accounts(user.id, now_utc()))).all()
    }
    if not set(insight.payload_json.get("source_account_ids", [])) <= active_ids:
        raise HTTPException(404, "Alert not found")
    row.read_at = row.read_at or now_utc()
    await db.commit()
    return {"id": row.id, "read_at": row.read_at}
