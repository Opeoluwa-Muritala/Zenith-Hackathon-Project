"""Bounded CSV statement parser; files are never persisted."""

import csv
import io
from datetime import datetime

from app.providers.base import ProviderError, ProviderTransaction

MAX_UPLOAD_BYTES = 2_000_000
MAX_ROWS = 10_000


class StatementUploadProvider:
    """Parse a strict UTF-8 CSV into normalised provider transactions."""

    def parse(self, data: bytes) -> list[ProviderTransaction]:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ProviderError("Statement exceeds 2 MB")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ProviderError("Statement must be UTF-8 CSV") from exc
        reader = csv.DictReader(io.StringIO(text))
        required = {"date", "amount_minor", "direction", "narration"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ProviderError("Missing required CSV columns")
        out = []
        for index, row in enumerate(reader):
            if index >= MAX_ROWS:
                raise ProviderError("Statement exceeds row limit")
            direction = row["direction"].lower()
            if direction not in {"credit", "debit"}:
                raise ProviderError("Invalid direction")
            amount = int(row["amount_minor"])
            if amount <= 0:
                raise ProviderError("Amount must be positive")
            out.append(
                ProviderTransaction(
                    row.get("id") or str(index),
                    datetime.fromisoformat(row["date"].replace("Z", "+00:00")),
                    amount,
                    direction,
                    row["narration"][:500],
                    row.get("category") or None,
                    int(row["balance_after_minor"]) if row.get("balance_after_minor") else None,
                )
            )
        return out
