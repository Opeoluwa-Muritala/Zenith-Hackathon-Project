"""Reference-rate acquisition and integer-only money conversion."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.ledger.service import as_utc
from app.models import FxRate

RATE_SCALE = 1_000_000


def rate_to_ppm(value: Decimal) -> int:
    if not value.is_finite() or not Decimal("0.000001") <= value <= Decimal("1000000"):
        raise ValueError("Invalid FX rate")
    return int((value * RATE_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def convert_minor(amount_minor: int, rate_ppm: int) -> int:
    return (amount_minor * rate_ppm + RATE_SCALE // 2) // RATE_SCALE


class FxProvider(Protocol):
    async def fetch_usd_ngn(self) -> Decimal: ...


class HttpFxProvider:
    async def fetch_usd_ngn(self) -> Decimal:
        settings = get_settings()
        if not settings.fx_provider_url:
            raise RuntimeError("FX provider is not configured")
        if settings.environment == "production" and not settings.fx_provider_url.startswith(
            "https://"
        ):
            raise RuntimeError("FX provider URL must use HTTPS")
        headers = (
            {"Authorization": f"Bearer {settings.fx_provider_key}"}
            if settings.fx_provider_key
            else {}
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(settings.fx_provider_url, headers=headers)
                response.raise_for_status()
                return Decimal(str(response.json()["rate"]))
        except (httpx.HTTPError, KeyError, ValueError, InvalidOperation) as exc:
            raise RuntimeError("FX reference rate unavailable") from exc


async def get_usd_ngn_rate(db: AsyncSession, supplied: Decimal | None) -> tuple[int, str]:
    settings = get_settings()
    if supplied is not None:
        try:
            return rate_to_ppm(supplied), "client"
        except ValueError as exc:
            raise HTTPException(422, "Invalid FX rate") from exc
    if not settings.fx_provider_url:
        raise HTTPException(422, "USD assets require an fx_rate when no FX provider is configured")
    cached = (
        await db.execute(
            select(FxRate)
            .where(
                FxRate.base == "USD",
                FxRate.quote == "NGN",
                FxRate.source == settings.fx_provider_name,
            )
            .order_by(FxRate.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    cached_at = as_utc(cached.fetched_at) if cached else None
    if cached and cached_at and now_utc() - cached_at < timedelta(hours=settings.fx_ttl_hours):
        return cached.rate, cached.source
    try:
        rate = rate_to_ppm(await HttpFxProvider().fetch_usd_ngn())
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, "FX reference rate unavailable") from exc
    db.add(
        FxRate(
            base="USD",
            quote="NGN",
            rate=rate,
            source=settings.fx_provider_name,
            fetched_at=now_utc(),
        )
    )
    return rate, settings.fx_provider_name
