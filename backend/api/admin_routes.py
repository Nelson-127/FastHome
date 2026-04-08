"""Admin JSON API (Basic auth)."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.deps import verify_admin_basic
from backend.schemas.requests import AdminRequestOut, AdminRequestPatch, RequestStatusApi
from backend.services.matching_service import match_listings
from backend.services.notify_service import notify_admins, notify_payment_success_for_user, send_user_message
from backend.services.payment_flow import MAX_VARIANTS, urgency_hours
from database.connection import get_session
from database.models import Listing, Request as RentRequest, RequestStatus, User
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_basic)])


class ListingOut(BaseModel):
    id: int
    source: str
    url: str
    district: str | None
    price: float | None
    rooms: str | None
    title: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_listing(cls, li: Listing) -> "ListingOut":
        return cls(
            id=li.id,
            source=li.source.value if hasattr(li.source, "value") else str(li.source),
            url=li.url,
            district=li.district,
            price=float(li.price) if li.price is not None else None,
            rooms=li.rooms,
            title=li.title,
        )


class AdminMessageBody(BaseModel):
    telegram_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1, max_length=3900)


@router.get("/requests", response_model=list[AdminRequestOut])
async def admin_list_requests(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AdminRequestOut]:
    stmt = select(RentRequest).options(joinedload(RentRequest.user)).order_by(RentRequest.id.desc()).limit(limit)
    if status:
        try:
            st = RequestStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
        stmt = stmt.where(RentRequest.status == st)
    rows = (await session.execute(stmt)).unique().scalars().all()
    out: list[AdminRequestOut] = []
    for r in rows:
        u = r.user
        out.append(
            AdminRequestOut(
                id=r.id,
                user_id=r.user_id,
                district=r.district,
                budget=float(r.budget),
                rooms=r.rooms,
                term=r.term,
                move_in_date=r.move_in_date,
                contact=r.contact,
                urgency=r.urgency,
                status=RequestStatusApi(r.status.value),
                created_at=r.created_at,
                telegram_id=u.telegram_id if u else None,
            )
        )
    return out


@router.get("/requests/{request_id}", response_model=AdminRequestOut)
async def admin_get_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
) -> AdminRequestOut:
    stmt = select(RentRequest).options(joinedload(RentRequest.user)).where(RentRequest.id == request_id)
    r = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404)
    u = r.user
    return AdminRequestOut(
        id=r.id,
        user_id=r.user_id,
        district=r.district,
        budget=float(r.budget),
        rooms=r.rooms,
        term=r.term,
        move_in_date=r.move_in_date,
        contact=r.contact,
        urgency=r.urgency,
        status=RequestStatusApi(r.status.value),
        created_at=r.created_at,
        telegram_id=u.telegram_id if u else None,
    )


@router.patch("/requests/{request_id}", response_model=AdminRequestOut)
async def admin_patch_request(
    request_id: int,
    body: AdminRequestPatch,
    session: AsyncSession = Depends(get_session),
) -> AdminRequestOut:
    stmt = select(RentRequest).options(joinedload(RentRequest.user)).where(RentRequest.id == request_id)
    r = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404)
    old_status = r.status
    if body.status is not None:
        r.status = RequestStatus(body.status.value)
    await session.commit()
    await session.refresh(r)
    u = r.user
    if (
        body.status is not None
        and body.status == RequestStatusApi.paid
        and old_status == RequestStatus.waiting_payment
        and u
    ):
        try:
            await notify_payment_success_for_user(
                u,
                r.id,
                max_variants=MAX_VARIANTS,
                hours=urgency_hours(r.urgency),
            )
            await notify_admins(f"✅ Заявка #{r.id} отмечена оплаченной (вручную).")
        except Exception:
            logger.exception("Notify user on manual paid failed request_id=%s", r.id)
    return AdminRequestOut(
        id=r.id,
        user_id=r.user_id,
        district=r.district,
        budget=float(r.budget),
        rooms=r.rooms,
        term=r.term,
        move_in_date=r.move_in_date,
        contact=r.contact,
        urgency=r.urgency,
        status=RequestStatusApi(r.status.value),
        created_at=r.created_at,
        telegram_id=u.telegram_id if u else None,
    )


@router.get("/requests/{request_id}/matches", response_model=list[ListingOut])
async def admin_request_matches(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[ListingOut]:
    r = await session.get(RentRequest, request_id)
    if not r:
        raise HTTPException(status_code=404)
    listings = await match_listings(session, r, limit=limit)
    return [ListingOut.from_orm_listing(li) for li in listings]


@router.post("/messages")
async def admin_send_message(body: AdminMessageBody) -> dict[str, str]:
    try:
        await send_user_message(body.telegram_id, body.text)
    except Exception as e:
        logger.exception("Admin send message failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"status": "sent"}
