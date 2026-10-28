"""Operator-only global rule promotion: python -m scripts.review_classification KEY CATEGORY."""

import argparse
import asyncio

from app.core.db import SessionLocal
from app.ledger.review import promote_reviewed_rule


async def promote(key: str, category: str) -> None:
    async with SessionLocal() as db:
        await promote_reviewed_rule(db, key, category)
        await db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review and promote an agreed classification rule")
    parser.add_argument("key", help="Normalized counterparty key reviewed by the operator")
    parser.add_argument("category")
    arguments = parser.parse_args()
    asyncio.run(promote(arguments.key, arguments.category))
