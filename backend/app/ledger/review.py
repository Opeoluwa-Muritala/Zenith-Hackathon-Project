"""Owner-scoped transfer review and operator-only global rule promotion."""

import hashlib
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.db import get_db
from app.core.security import current_user
from app.ledger.normalise import FETCH_CATEGORIES, counterparty_key
from app.models import (
    ClassificationCorrection,
    ReviewedGlobalRule,
    TransferSuggestion,
    User,
)

router = APIRouter(tags=["Classification review"])


async def promote_reviewed_rule(db: AsyncSession, key: str, category: str) -> ReviewedGlobalRule:
    """Operator service: no public route grants global-rule review privileges."""
    if category not in FETCH_CATEGORIES or key != counterparty_key(key) or not key:
        raise ValueError("Invalid normalized key or category")
    users = set(
        (
            await db.scalars(
                select(ClassificationCorrection.user_id).where(
                    ClassificationCorrection.counterparty_key == key,
                    ClassificationCorrection.category == category,
                    ClassificationCorrection.confirmed.is_(True),
                )
            )
        ).all()
    )
    if len(users) < 2:
        raise ValueError("Two independent users must agree before review")
    digest = hashlib.sha256(key.encode()).hexdigest()
    rule = await db.scalar(
        select(ReviewedGlobalRule).where(ReviewedGlobalRule.narration_hash == digest)
    )
    if rule is None:
        rule = ReviewedGlobalRule(narration_hash=digest, category=category, reviewed_at=now_utc())
        db.add(rule)
    else:
        rule.category, rule.reviewed_at = category, now_utc()
    await db.flush()
    return rule


@router.get("/transfer-suggestions")
async def list_suggestions(
    user: Annotated[User, Depends(current_user)], db: Annotated[AsyncSession, Depends(get_db)]
) -> list[dict]:
    rows = await db.scalars(select(TransferSuggestion).where(TransferSuggestion.user_id == user.id))
    return [
        {"id": row.id, "counterparty": row.counterparty_key, "kind": row.kind, "status": row.status}
        for row in rows
    ]


@router.post("/transfer-suggestions/{suggestion_id}/{action}")
async def review_suggestion(
    suggestion_id: UUID,
    action: Literal["confirm", "dismiss"],
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.scalar(
        select(TransferSuggestion)
        .where(TransferSuggestion.id == suggestion_id, TransferSuggestion.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Suggestion not found")
    row.status = "confirmed" if action == "confirm" else "dismissed"
    if row.status == "confirmed" and row.kind == "family":
        from app.models import CategoryRule

        rule = await db.scalar(
            select(CategoryRule).where(
                CategoryRule.user_id == user.id,
                CategoryRule.counterparty_key == row.counterparty_key,
            )
        )
        if rule is None:
            db.add(
                CategoryRule(
                    user_id=user.id,
                    counterparty_key=row.counterparty_key,
                    category="Transfers & Family",
                    created_at=now_utc(),
                )
            )
        # An existing explicit user correction has higher priority than this suggestion.
    await db.commit()
    return {"id": row.id, "status": row.status}
