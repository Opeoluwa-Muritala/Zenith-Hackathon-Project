"""Calendar reminders and valuation for user-maintained assets."""

import calendar
from datetime import datetime, timedelta

from app.assets.fx import convert_minor
from app.models import ManualAsset, UpdateCadence


def next_reminder(start: datetime, cadence: UpdateCadence) -> datetime:
    if cadence == UpdateCadence.biweekly:
        return start + timedelta(days=14)
    month = start.month + 1
    year = start.year
    if month == 13:
        month, year = 1, year + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def asset_value_ngn_minor(asset: ManualAsset) -> int:
    if asset.currency == "NGN":
        return asset.amount_minor
    if asset.currency == "USD" and asset.fx_rate_used is not None:
        return convert_minor(asset.amount_minor, asset.fx_rate_used)
    raise ValueError("USD asset has no stored FX rate")
