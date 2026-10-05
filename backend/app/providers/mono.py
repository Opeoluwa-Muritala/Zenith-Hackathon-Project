"""Mono Connect v2 client with bounded retries and redacted errors."""

import asyncio
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.providers.base import (
    AggregatorProvider,
    ProviderError,
    ProviderNotReady,
    ProviderTransaction,
    ProviderUnavailable,
)


class MonoProvider(AggregatorProvider):
    """Call verified Mono v2 endpoints without logging financial payloads."""

    def __init__(
        self,
        secret_key: str,
        base_url: str = "https://api.withmono.com",
        client: httpx.AsyncClient | None = None,
    ):
        if not secret_key:
            raise ValueError("MONO_SECRET_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"mono-sec-key": secret_key, "accept": "application/json"},
            timeout=httpx.Timeout(15),
        )

    async def _request(self, method, path, **kwargs):
        for attempt in range(3):
            try:
                response = await self.client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                if attempt == 2:
                    raise ProviderUnavailable("Mono request unavailable") from exc
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                raise ProviderUnavailable("Mono temporarily unavailable")
            if response.is_error:
                raise ProviderError(f"Mono rejected request ({response.status_code})")
            return response.json()
        raise ProviderUnavailable("Mono request unavailable")

    async def initiate(self, name, email, ref, redirect_url):
        payload = await self._request(
            "POST",
            "/v2/accounts/initiate",
            json={
                "customer": {"name": name, "email": email},
                "meta": {"ref": ref},
                "scope": "auth",
                "redirect_url": redirect_url,
            },
        )
        return payload["data"]["mono_url"]

    async def exchange(self, code):
        payload = await self._request("POST", "/v2/accounts/auth", json={"code": code})
        return payload.get("id") or payload.get("data", {}).get("id")

    async def details(self, account_id, realtime=False):
        return await self._request(
            "GET",
            f"/v2/accounts/{account_id}",
            headers={"x-real-time": "true"} if realtime else None,
        )

    async def transactions(self, account_id, start, end):
        details = await self.details(account_id)
        meta = details.get("data", {}).get("meta", details.get("meta", {}))
        if meta.get("data_status") not in {
            "AVAILABLE",
            "PARTIAL",
        } or "transactions" not in meta.get("retrieved_data", ["transactions"]):
            raise ProviderNotReady("Mono transaction data is not ready")
        path = f"/v2/accounts/{account_id}/transactions"
        params = {"start": start.date().isoformat(), "end": end.date().isoformat()}
        rows = []
        while path:
            payload = await self._request("GET", path, params=params)
            params = None
            rows.extend(payload.get("data", []))
            nxt = payload.get("meta", {}).get("next")
            if nxt:
                parsed = urlparse(nxt)
                if f"{parsed.scheme}://{parsed.netloc}" != self.base_url:
                    raise ProviderError("Mono returned an invalid pagination URL")
                path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            else:
                path = ""
        return [
            ProviderTransaction(
                str(r.get("id")),
                datetime.fromisoformat(r["date"].replace("Z", "+00:00")),
                int(r["amount"]),
                r["type"],
                str(r.get("narration", ""))[:500],
                r.get("category"),
                int(r["balance"]) if r.get("balance") is not None else None,
            )
            for r in rows
        ]

    async def categorise(self, account_id):
        await self._request("POST", f"/v2/accounts/{account_id}/transactions/categorise")

    async def unlink(self, account_id):
        await self._request("POST", f"/v2/accounts/{account_id}/unlink")
