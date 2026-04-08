"""Upsert listings into PostgreSQL (dedupe by url)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Listing, ListingSource

logger = logging.getLogger(__name__)


async def upsert_listings(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Returns number of attempted inserts (conflicts ignored)."""
    n = 0
    for row in rows:
        stmt = (
            insert(Listing)
            .values(
                source=row["source"],
                url=row["url"],
                district=row.get("district"),
                price=row.get("price"),
                rooms=row.get("rooms"),
                title=row.get("title"),
                raw_meta=row.get("raw_meta"),
            )
            .on_conflict_do_nothing(index_elements=["url"])
        )
        await session.execute(stmt)
        n += 1
    await session.commit()
    logger.info("Listing upsert batch size=%s", n)
    return n


async def run_all_parsers(session: AsyncSession) -> int:
    print("🔥 RUN_ALL_PARSERS STARTED")
    from parsing.myhome_parser import MyHomeParser
    from parsing.ss_ge_parser import SsGeParser

    total = 0
    #for cls in (SsGeParser, MyHomeParser):
    for cls in (MyHomeParser,):
        try:
            items = await cls().parse()
            print(f"✅ {cls.__name__} parsed: {len(items)} items")
            total += await upsert_listings(session, items)
        except Exception:
            logger.exception("Parser failed: %s", cls.__name__)
    return total
