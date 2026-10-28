"""Mono BVN iGree Lookup client."""

from app.providers.mono import MonoProvider


class MonoLookupProvider(MonoProvider):
    def __init__(self, secret_key: str, base_url: str = "https://api.withmono.com"):
        super().__init__(secret_key, base_url)

    async def initiate_lookup(self, bvn: str):
        payload = await self._request(
            "POST",
            "/v2/lookup/bvn/initiate",
            retry=False,
            json={"bvn": bvn, "scope": "bank_accounts"},
        )
        data = payload.get("data", {})
        if (
            not isinstance(data, dict)
            or not data.get("session_id")
            or not isinstance(data.get("methods"), list)
        ):
            raise ValueError("Invalid lookup response")
        return data["session_id"], data["methods"]

    async def verify_lookup(self, session_id: str, method: str, phone_number: str | None = None):
        body = {"method": method}
        if phone_number is not None:
            body["phone_number"] = phone_number
        return await self._request(
            "POST",
            "/v2/lookup/bvn/verify",
            retry=False,
            headers={"x-session-id": session_id},
            json=body,
        )

    async def lookup_details(self, session_id: str, otp: str):
        payload = await self._request(
            "POST",
            "/v2/lookup/bvn/details",
            retry=False,
            headers={"x-session-id": session_id},
            json={"otp": otp},
        )
        data = payload.get("data")
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError("Invalid lookup account response")
        return data
