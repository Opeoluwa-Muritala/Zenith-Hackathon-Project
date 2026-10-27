"""Groq chat-completions client and a deterministic fake for tests."""

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ToolCall:
    """A model-proposed tool call; the backend still validates every argument."""

    id: str
    name: str
    arguments: dict
    arguments_valid: bool = True


@dataclass(frozen=True)
class LLMResult:
    """Text, tool requests and usage from a non-streaming completion."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    assistant_message: dict | None = None
    model: str = ""


class LLMClient(Protocol):
    """Provider-neutral completion boundary for phrasing and tool selection."""

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResult: ...


class FakeLLMClient:
    """Scriptable deterministic response queue that never makes network calls."""

    def __init__(self, results: list[LLMResult] | None = None):
        self.results = list(
            results
            or [LLMResult(text='{"title":"A clear picture","body":"Review the verified details."}')]
        )
        self.calls: list[dict] = []

    async def complete(self, **request) -> LLMResult:
        """Record the exact minimised payload and return the next scripted reply."""
        self.calls.append(request)
        return self.results.pop(0) if self.results else LLMResult(text="I cannot verify that yet.")


class GroqClient:
    """Call Groq with bounded retries."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout_s: float,
        client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise ValueError("GROQ_KEY is required")
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.http = client or httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(timeout_s))
        self._headers = headers
        self._owns_client = client is None

    async def close(self) -> None:
        """Close the internally owned shared HTTP client."""
        if self._owns_client:
            await self.http.aclose()

    async def _post(self, path: str, payload: dict) -> dict:
        """Retry only HTTP 429 and 5xx responses; never expose provider bodies."""
        for attempt in range(3):
            try:
                response = await self.http.post(
                    f"{self.base_url}{path}", json=payload, headers=self._headers
                )
            except httpx.RequestError as exc:
                raise RuntimeError("AI provider is unavailable") from exc
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError("AI provider is temporarily unavailable")
            if response.is_error:
                raise RuntimeError(f"AI provider rejected request ({response.status_code})")
            try:
                body = response.json()
            except ValueError as exc:
                raise RuntimeError("AI provider returned invalid JSON") from exc
            if body.get("error"):
                raise RuntimeError("AI provider returned an error")
            return body
        raise RuntimeError("AI provider is temporarily unavailable")

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        """Call the OpenAI-compatible endpoint and normalise tool calls and usage."""
        if not model:
            raise ValueError("AI model is required")
        groq_tools = [
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item["description"],
                    "parameters": item["input_schema"],
                },
            }
            for item in tools
        ]
        payload: dict[str, object] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if groq_tools:
            payload["tools"] = groq_tools
        body = await self._post("/chat/completions", payload)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("AI provider returned no completion")
        choice = choices[0]
        if choice.get("error"):
            raise RuntimeError("AI model returned an error")
        reason = choice.get("finish_reason")
        if reason in {"length", "content_filter", "error"}:
            raise RuntimeError("AI model did not complete a usable response")
        message = choice.get("message") or {}
        raw_calls = message.get("tool_calls") or []
        calls = []
        for call in raw_calls:
            function = call.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be an object")
                valid = True
            except (json.JSONDecodeError, ValueError, TypeError):
                arguments, valid = {}, False
            calls.append(
                ToolCall(str(call.get("id", "")), str(function.get("name", "")), arguments, valid)
            )
        usage = body.get("usage") or {}
        text = message.get("content")
        return LLMResult(
            text=text if isinstance(text, str) else "",
            tool_calls=tuple(calls),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            assistant_message=message,
            model=str(body.get("model") or model),
        )

    async def supports_tools(self, model: str) -> bool:
        """Check that the configured chat model is available in Groq's catalogue."""
        response = await self.http.get(
            f"{self.base_url}/models",
            headers=self._headers,
        )
        if response.is_error:
            return False
        data = response.json().get("data", [])
        return any(item.get("id") == model for item in data if isinstance(item, dict))
