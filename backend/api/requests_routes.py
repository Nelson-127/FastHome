"""Public request API (called by bot)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_internal_key
from backend.schemas.requests import RequestCreate, RequestOut
from backend.services.notify_service import notify_admins_new_request
from backend.services.request_service import create_request, get_request_for_telegram
from database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestOut)
async def post_request(
    body: RequestCreate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_internal_key),
) -> RequestOut:
    req = await create_request(
        session,
        telegram_id=body.telegram_id,
        telegram_username=body.telegram_username,
        language=body.language,
        district=body.district,
        budget=body.budget,
        rooms=body.rooms,
        term=body.term,
        move_in_date=body.move_in_date,
        contact=body.contact,
        urgency=body.urgency,
    )
    await session.commit()
    logger.info("Request created id=%s telegram_id=%s", req.id, body.telegram_id)
    try:
        await notify_admins_new_request(req.id, req.district, body.telegram_username)
    except Exception:
        logger.exception("Admin notify failed for request %s", req.id)
    await session.refresh(req)
    data = RequestOut.model_validate(req)
    return data


@router.get("/{request_id}", response_model=RequestOut)
async def get_request(
    request_id: int,
    telegram_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_internal_key),
) -> RequestOut:
    req = await get_request_for_telegram(session, request_id, telegram_id)
    if not req:
        raise HTTPException(status_code=404, detail="Not found")
    return RequestOut.model_validate(req)
