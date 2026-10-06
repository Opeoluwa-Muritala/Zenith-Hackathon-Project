"""Bounded, read-only chat orchestration with deterministic fallback and verification."""

import asyncio
import json
import logging
import re
import time

from app.ai.audit import record
from app.ai.budget import budget_allowed
from app.ai.chat.tools import TOOL_NAMES, TOOLS, calculate
from app.ai.client import LLMClient
from app.ai.prompts import CHAT_PROMPT_VERSION, CHAT_SYSTEM, facts_message
from app.ai.redaction import redact_user_text, tool_input
from app.ai.verify import verify_numbers
from app.core.config import get_settings

logger = logging.getLogger("cashlens.ai.chat")
MAX_TOOL_CALLS = 5
MAX_ROUND_TRIPS = 3
DISTRESS_RE = re.compile(
    r"\b(can't afford food|cannot afford food|can't afford rent|cannot afford rent|"
    r"can't pay rent|cannot pay rent|"
    r"self[- ]harm|suicid(?:e|al))\b",
    re.I,
)
OUT_OF_SCOPE_RE = re.compile(
    r"\b(legal advice|medical|hack(?:ing)?|password|"
    r"someone else'?s account|another person'?s account)\b",
    re.I,
)


def _fallback(results: list[dict]) -> str:
    """Summarise confirmed aggregate values without introducing figures."""
    if not results:
        return (
            "I couldn't verify those figures, so here is what I can confirm: "
            "I don't have enough connected account data to answer that yet."
        )
    parts = []
    for item in results[:5]:
        result = item["result"]
        amount = (
            result.get("daily_allowance_minor")
            or result.get("available_minor")
            or result.get("total_minor")
        )
        if amount is not None:
            label = "verified amount"
            parts.append(f"{item['name']}: {label} {amount}.")
        elif result.get("verdict"):
            parts.append(f"Affordability result: {result['verdict']}.")
        elif result.get("status"):
            parts.append(f"Current status: {result['status']}.")
        else:
            parts.append(f"{item['name']} returned verified aggregate data.")
    return "I couldn't verify the wording, so here is what I can confirm: " + " ".join(parts)


def _safety_reply(question: str) -> str | None:
    """Handle distress and clearly out-of-scope topics without a model call."""
    if DISTRESS_RE.search(question):
        return (
            "I'm sorry you're facing this. I won't try to optimise this situation. "
            "Please consider contacting someone you trust or local support services."
        )
    if OUT_OF_SCOPE_RE.search(question):
        return (
            "I can help explain your own connected financial data, "
            "but I can't help with that request."
        )
    if re.search(
        r"\b(my (friend|spouse|parent|boss)|someone else|another person)\b", question, re.I
    ):
        return "I can only see the accounts you have connected."
    return None


def _chat_message(text: str) -> dict:
    """Wrap untrusted user text as data after removing obvious identifiers."""
    return {"role": "user", "content": facts_message({"question": redact_user_text(text)})}


async def converse(question, view, settings, now, db, user_id, client: LLMClient | None):
    """Run up to five aggregate tools and three model round trips, then verify figures."""
    config = get_settings()
    safety = _safety_reply(question)
    if safety:
        return {
            "reply": safety,
            "tools_used": [],
            "verification_passed": True,
            "facts": [],
            "ai_enabled": True,
            "affordability": None,
        }
    if client is None:
        return {
            "reply": (
                "Smart chat is off. Turn on Smart insights and chat in Settings "
                "to ask about your finances."
            ),
            "tools_used": [],
            "verification_passed": True,
            "facts": [],
            "ai_enabled": False,
            "affordability": None,
        }
    if not await budget_allowed(db, user_id, now):
        return {
            "reply": (
                "Today's AI usage limit has been reached. You can still review "
                "your verified insights and summaries."
            ),
            "tools_used": [],
            "verification_passed": True,
            "facts": [],
            "ai_enabled": True,
            "affordability": None,
        }
    messages = [_chat_message(question)]
    tools_used: list[str] = []
    facts: list[dict] = []
    started = time.monotonic()
    input_tokens = output_tokens = 0
    verification = False
    fallback_used = False
    response_text = ""
    actual_model = config.ai_chat_model
    tool_attempts = 0
    try:
        for round_index in range(MAX_ROUND_TRIPS):
            response = await asyncio.wait_for(
                client.complete(
                    model=config.ai_chat_model,
                    system=CHAT_SYSTEM,
                    messages=messages,
                    tools=TOOLS,
                    max_tokens=config.ai_max_tokens_chat,
                    temperature=0.3,
                ),
                timeout=config.ai_request_timeout_s,
            )
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens
            actual_model = response.model or actual_model
            if not response.tool_calls:
                response_text = response.text.strip()
                break
            tool_attempts += len(response.tool_calls)
            if tool_attempts > MAX_TOOL_CALLS:
                fallback_used = True
                response_text = _fallback(facts)
                break
            assistant_message = response.assistant_message or {
                "role": "assistant",
                "content": response.text or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in response.tool_calls
                ],
            }
            messages.append(assistant_message)
            for call in response.tool_calls:
                if call.name not in TOOL_NAMES:
                    raise ValueError("Unknown tool request")
                try:
                    if not call.arguments_valid:
                        raise ValueError("Invalid JSON arguments")
                    result = calculate(call.name, call.arguments, view, settings, now)
                except ValueError:
                    if not call.id:
                        raise
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": (
                                "Invalid tool arguments. Retry once with the exact function "
                                "schema; do not estimate a result."
                            ),
                        }
                    )
                    continue
                facts.append(tool_input(call.name, result))
                tools_used.append(call.name)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            if round_index == MAX_ROUND_TRIPS - 1:
                fallback_used = True
                response_text = _fallback(facts)
        if response_text and verify_numbers(response_text, facts):
            verification = True
        else:
            fallback_used = True
            response_text = _fallback(facts)
            verification = verify_numbers(response_text, facts)
        disclaimer = "Educational information, not financial advice."
        if (
            re.search(r"\b(save|saving|invest|investment|wealth|treasury bill)\b", question, re.I)
            and disclaimer not in response_text
        ):
            response_text = response_text.rstrip() + " " + disclaimer
    except Exception as exc:
        logger.info("ai_chat_fallback", extra={"error_type": type(exc).__name__})
        fallback_used = True
        response_text = _fallback(facts)
        verification = verify_numbers(response_text, facts)
    await record(
        db,
        user_id=user_id,
        feature="chat",
        model=actual_model,
        prompt_version=CHAT_PROMPT_VERSION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=int((time.monotonic() - started) * 1000),
        verification_passed=verification,
        fallback_used=fallback_used,
        tools_used=tools_used,
        now=now,
    )
    affordability = next(
        (fact["result"] for fact in facts if fact["name"] == "affordability_check"), None
    )
    return {
        "reply": response_text,
        "tools_used": tools_used,
        "verification_passed": verification,
        "facts": facts,
        "ai_enabled": True,
        "affordability": affordability,
    }
