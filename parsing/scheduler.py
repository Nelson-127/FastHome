"""APScheduler jobs: periodic parsing and optional maintenance hooks."""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)



def start_parse_scheduler(session_factory: Any, *, minutes: int = 18) -> AsyncIOScheduler | None:
    """Fetch listings every N minutes. No-op if database session factory is unavailable."""
    if session_factory is None:
        logger.warning("Parse scheduler not started: no database session factory")
        return None

    from parsing.ingest import run_all_parsers

    scheduler = AsyncIOScheduler()

    async def job() -> None:
        async with session_factory() as session:
            try:
                n = await run_all_parsers(session)
                from backend.services.matching_service import match_listings
                from backend.services.notify_service import notify_matches_for_user
                from database.models import Request, User
                from sqlalchemy import select

                requests = (await session.execute(select(Request))).scalars().all()

                for req in requests:
                    matches = await match_listings(session, req)

                    if not matches:
                        continue

                    user = await session.get(User, req.user_id)
                    if not user:
                        continue

                    await notify_matches_for_user(session, user, matches)

                logger.info("Parse job finished, upserts=%s", n)
            except Exception:
                logger.exception("Parse job failed")
            try:
                from backend.services.matching_service import match_listings
                from backend.services.notify_service import notify_matches_for_user
                from database.models import Request, User
                from sqlalchemy import select
            except Exception:
                logger.exception("Matching job failed")

    scheduler.add_job(job, "interval", minutes=minutes, id="listing_parse", replace_existing=True)
    scheduler.start()
    return scheduler


def start_payment_sweep_scheduler(session_factory: Any, *, minutes: int = 7) -> AsyncIOScheduler | None:
    if session_factory is None:
        return None

    from backend.services.pending_payment_sweep import sweep_pending

    scheduler = AsyncIOScheduler()

    async def job() -> None:
        async with session_factory() as session:
            try:
                await sweep_pending(session)
            except Exception:
                logger.exception("Payment sweep failed")

    scheduler.add_job(job, "interval", minutes=minutes, id="payment_sweep", replace_existing=True)
    scheduler.start()
    return scheduler
