from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Listing, Request as RentRequest


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _rooms_key(rooms: str | None) -> int | None:
    if not rooms:
        return None
    m = re.search(r"(\d+)", str(rooms))
    return int(m.group(1)) if m else None


def match_score(req: RentRequest, listing: Listing) -> float:
    score = 0.0

    # --- район ---
    rd = _normalize(req.district)
    ld = _normalize(listing.district)

    if rd and ld:
        if rd in ld or ld in rd:
            score += 40
        else:
            if set(rd.split()) & set(ld.split()):
                score += 15
            else:
                return 0  # ❗ если район не совпал — сразу выкидываем

    # --- цена ---
    if listing.price is not None:
        budget = float(req.budget)
        price = float(listing.price)

        if price > budget * 1.2:
            return 0  # ❗ слишком дорого — сразу мимо

        diff = abs(price - budget) / budget
        score += 40 * (1 - min(diff, 1))

    # --- комнаты ---
    rr = _rooms_key(req.rooms)
    lr = _rooms_key(listing.rooms)

    if rr and lr:
        if rr == lr:
            score += 20
        else:
            return 0  # ❗ если не совпали — отсекаем

    return score


async def match_listings(session: AsyncSession, request: RentRequest, *, limit: int = 10) -> list[Listing]:
    budget = float(request.budget)
    max_price = Decimal(str(budget * 1.2))

    stmt = (
        select(Listing)
        .where(Listing.price.is_not(None))
        .where(Listing.price <= max_price)
        .limit(500)
    )

    rows = (await session.execute(stmt)).scalars().all()

    scored = []
    for li in rows:
        score = match_score(request, li)
        if score > 0:
            scored.append((score, li))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [li for _, li in scored[:limit]]