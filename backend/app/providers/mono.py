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

    async def _request(self, method, path, *, retry=True, include_job_headers=False, **kwargs):
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            try:
                response = await self.client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                if attempt == attempts - 1:
                    raise ProviderUnavailable("Mono request unavailable") from exc
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < attempts - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise ProviderUnavailable("Mono temporarily unavailable")
            if response.is_error:
                raise ProviderError(f"Mono rejected request ({response.status_code})")
            try:
                payload = response.json()
                if include_job_headers and isinstance(payload, dict):
                    payload["_realtime"] = {
                        "job_status": response.headers.get("x-job-status", "").lower(),
                        "has_new_data": response.headers.get("x-has-new-data", "").lower(),
                    }
                return payload
            except ValueError:
                raise ProviderUnavailable("Mono returned an invalid response") from None
        raise ProviderUnavailable("Mono request unavailable")

    async def institutions(self) -> list[dict]:
        payload = await self._request("GET", "/v3/institutions", params={"scope": "financial_data"})
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ProviderError("Mono returned invalid institution coverage")
        return rows

    async def initiate(self, name, email, ref, redirect_url, institution=None, account_number=None):
        body = {
            "customer": {"name": name, "email": email},
            "meta": {"ref": ref},
            "scope": "auth",
            "redirect_url": redirect_url,
        }
        if institution:
            body["institution"] = dict(institution)
            if account_number:
                body["institution"]["account_number"] = account_number
                body["check_account_match"] = True
        payload = await self._request(
            "POST",
            "/v2/accounts/initiate",
            retry=False,
            json=body,
        )
        return payload["data"]["mono_url"]

    async def exchange(self, code):
        payload = await self._request("POST", "/v2/accounts/auth", retry=False, json={"code": code})
        return payload.get("id") or payload.get("data", {}).get("id")

    async def details(self, account_id, realtime=False):
        return await self._request(
            "GET",
            f"/v2/accounts/{account_id}",
            headers={"x-realtime": "true"} if realtime else None,
        )

    async def balance(self, account_id: str, realtime: bool = False) -> dict:
        """Return Mono's balance response; NGN values are in kobo."""
        return await self._request(
            "GET",
            f"/v2/accounts/{account_id}/balance",
            retry=not realtime,
            include_job_headers=realtime,
            headers={"x-realtime": "true"} if realtime else None,
        )

    async def transactions(self, account_id, start, end):
        details = await self.details(account_id)
        meta = details.get("data", {}).get("meta", details.get("meta", {}))
        if meta.get("data_status") not in {
            "AVAILABLE",
            "PARTIAL",
        } or "transactions" not in meta.get("retrieved_data", []):
            raise ProviderNotReady("Mono transaction data is not ready")
        path = f"/v2/accounts/{account_id}/transactions"
        params = {"start": start.date().isoformat(), "end": end.date().isoformat()}
        rows = []
        seen = set()
        while path:
            if path in seen or len(seen) >= 100:
                raise ProviderError("Mono returned invalid transaction pagination")
            seen.add(path)
            payload = await self._request("GET", path, params=params)
            params = None
            rows.extend(payload.get("data", []))
            nxt = payload.get("meta", {}).get("next")
            if nxt:
                parsed = urlparse(nxt)
                if (
                    f"{parsed.scheme}://{parsed.netloc}" != self.base_url
                    or parsed.path != f"/v2/accounts/{account_id}/transactions"
                    or parsed.fragment
                ):
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
                str(r.get("narration", "")),
                r.get("category"),
                int(r["balance"]) if r.get("balance") is not None else None,
            )
            for r in rows
        ]

    async def categorise(self, account_id):
        await self._request("POST", f"/v2/accounts/{account_id}/transactions/categorise")

    async def unlink(self, account_id):
        await self._request("POST", f"/v2/accounts/{account_id}/unlink")
