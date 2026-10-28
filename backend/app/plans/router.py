"""Public plan state and upgrade-intent APIs; no payment operations."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import current_user
from app.models import UpgradeTapEvent, User
from app.plans.service import plan_for, trial_status

router = APIRouter(tags=["Plans"])


class PlanResponse(BaseModel):
    tier: Literal["free", "sme"]
    paid_sme: bool
    trial_status: Literal["not_started", "active", "expired", "paid"]
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    free_live_account_limit: int
    entitlements: dict[str, bool]


class UpgradeTapRequest(BaseModel):
    surface: Literal[
        "home",
        "report",
        "business_separator",
        "alerts",
        "account_limit",
        "trial_expired",
        "settings",
    ]
    desired_tier: Literal["sme"] = "sme"


class UpgradeTapResponse(BaseModel):
    status: Literal["recorded"]


def response(plan, now: datetime) -> dict:
    paid = plan.paid_sme
    status = trial_status(plan, now)
    return {
        "tier": "sme" if paid else "free",
        "paid_sme": paid,
        "trial_status": status,
        "trial_started_at": plan.trial_started_at,
        "trial_ends_at": plan.trial_ends_at,
        "free_live_account_limit": get_settings().free_live_account_limit,
        "entitlements": {
            "statement_upload": True,
            "manual_assets": True,
            "budgets_and_categories": True,
            "continuous_live_sync": paid,
            "multiple_banks": paid,
            "business_personal_separation": paid,
            "lender_ready_reports": paid,
            "alerts": paid,
            "team_access": paid,
        },
    }


@router.get("/plan", response_model=PlanResponse)
async def get_plan(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    now = now_utc()
    plan = await plan_for(db, user.id, now)
    await db.commit()
    return response(plan, now)


@router.post("/billing/upgrade-events", status_code=202, response_model=UpgradeTapResponse)
async def record_upgrade_tap(
    body: UpgradeTapRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    db.add(
        UpgradeTapEvent(
            user_id=user.id,
            surface=body.surface,
            desired_tier=body.desired_tier,
            occurred_at=now_utc(),
        )
    )
    await db.commit()
    return {"status": "recorded"}
