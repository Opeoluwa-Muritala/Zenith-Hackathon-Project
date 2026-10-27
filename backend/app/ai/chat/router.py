"""Authenticated opt-in AI settings and read-only chat endpoints."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import chat_rate_allowed
from app.ai.chat.orchestrator import converse
from app.ai.client_factory import client_for
from app.ai.redaction import redact_user_text
from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import current_user
from app.ledger.service import ledger_view
from app.models import AssistantConversation, AssistantMessage, User, UserSettings

router = APIRouter(tags=["AI"])


class ChatRequest(BaseModel):
    """One user question, optionally attached to an existing conversation."""

    conversation_id: UUID | None = Field(
        default=None, description="Opaque ID of an owned chat, if continuing."
    )
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="Question about the signed-in user's connected financial data.",
    )


class AiPreferenceRequest(BaseModel):
    """Whether the user opts in to model-powered wording and chat."""

    enabled: bool = Field(
        description="Opt in to sending minimised aggregates to the configured language model."
    )


async def user_settings(db: AsyncSession, user_id: UUID) -> UserSettings:
    """Load preferences or construct safe defaults for an existing user."""
    row = await db.get(UserSettings, user_id)
    if row is None:
        row = UserSettings(
            user_id=user_id,
            safe_buffer_minor=500_000,
            payday_hint=None,
            discretionary_categories=["food", "shopping", "entertainment", "transport"],
            nominal_tbill_rate_bps=1500,
            ai_enabled=False,
        )
        db.add(row)
        await db.flush()
    return row


@router.patch("/settings/ai")
async def set_ai_preference(
    body: AiPreferenceRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist user opt-in; disabling AI immediately deletes their chat history."""
    row = await user_settings(db, user.id)
    row.ai_enabled = body.enabled
    if not body.enabled:
        conversations = select(AssistantConversation.id).where(
            AssistantConversation.user_id == user.id
        )
        await db.execute(
            delete(AssistantMessage).where(AssistantMessage.conversation_id.in_(conversations))
        )
        await db.execute(
            delete(AssistantConversation).where(AssistantConversation.user_id == user.id)
        )
    await db.commit()
    return {"ai_enabled": row.ai_enabled, "chat_history_deleted": not body.enabled}


@router.post("/ai/chat")
async def ask_money(
    body: ChatRequest,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer through bounded aggregate tools, with graceful disabled and budget states."""
    now = now_utc()
    preferences = await user_settings(db, user.id)
    if not get_settings().ai_enabled_global or not preferences.ai_enabled:
        return {
            "conversation_id": body.conversation_id,
            "reply": (
                "Smart chat is off. Turn on Smart insights and chat in Settings "
                "to ask about your finances."
            ),
            "tools_used": [],
            "verification_passed": True,
            "ai_enabled": False,
            "facts": [],
            "affordability": None,
        }
    if not getattr(request.app.state, "ai_chat_available", True):
        return {
            "conversation_id": body.conversation_id,
            "reply": (
                "Smart chat is temporarily unavailable for the configured model. "
                "Your rule-based insights remain available."
            ),
            "tools_used": [],
            "verification_passed": True,
            "ai_enabled": True,
            "facts": [],
            "affordability": None,
        }
    if not chat_rate_allowed(user.id, now):
        return {
            "conversation_id": body.conversation_id,
            "reply": (
                "You have reached the chat request limit for this minute. Please try again shortly."
            ),
            "tools_used": [],
            "verification_passed": True,
            "ai_enabled": True,
            "facts": [],
            "affordability": None,
        }
    conversation = None
    if body.conversation_id:
        conversation = (
            await db.execute(
                select(AssistantConversation).where(
                    AssistantConversation.id == body.conversation_id,
                    AssistantConversation.user_id == user.id,
                    AssistantConversation.expires_at > now,
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = AssistantConversation(
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=get_settings().assistant_retention_days),
        )
        db.add(conversation)
        await db.flush()
    view, settings = await ledger_view(db, user.id, now)
    response = await converse(body.message, view, settings, now, db, user.id, client_for())
    redacted_question = redact_user_text(body.message)
    db.add(
        AssistantMessage(
            conversation_id=conversation.id,
            role="user",
            content_redacted=redacted_question,
            tool_names=[],
            created_at=now,
        )
    )
    db.add(
        AssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
            content_redacted=redact_user_text(response["reply"]),
            tool_names=response["tools_used"],
            created_at=now,
        )
    )
    conversation.expires_at = now + timedelta(days=get_settings().assistant_retention_days)
    await db.commit()
    return {"conversation_id": conversation.id, **response}


@router.get("/ai/chat/{conversation_id}")
async def get_chat(
    conversation_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return bounded text history for one conversation owned by the user."""
    conversation = (
        await db.execute(
            select(AssistantConversation).where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user.id,
                AssistantConversation.expires_at > now_utc(),
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    rows = (
        await db.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation.id)
            .order_by(AssistantMessage.created_at)
            .limit(100)
        )
    ).scalars()
    return {
        "conversation_id": conversation.id,
        "messages": [
            {"role": row.role, "text": row.content_redacted, "tools_used": row.tool_names}
            for row in rows
        ],
    }


@router.delete("/ai/chat/{conversation_id}", status_code=204)
async def delete_chat(
    conversation_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete an owned conversation and all its messages."""
    conversation = (
        await db.execute(
            select(AssistantConversation).where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    await db.execute(
        delete(AssistantMessage).where(AssistantMessage.conversation_id == conversation.id)
    )
    await db.delete(conversation)
    await db.commit()
