"""Minimal admin HTML UI (Basic auth)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.deps import verify_admin_basic
from core.config import get_settings
from database.connection import get_session
from database.models import Request as RentRequest
from backend.services.matching_service import match_listings

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

router = APIRouter(prefix="/admin/ui", tags=["admin-ui"], dependencies=[Depends(verify_admin_basic)])


@router.get("/", response_class=HTMLResponse)
async def admin_home(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    stmt = select(RentRequest).options(joinedload(RentRequest.user)).order_by(RentRequest.id.desc()).limit(100)
    rows = (await session.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse(
        "requests_list.html",
        {"request": request, "rows": rows},
    )


@router.get("/requests/{request_id}", response_class=HTMLResponse)
async def admin_request_detail(
    request: Request,
    request_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    stmt = select(RentRequest).options(joinedload(RentRequest.user)).where(RentRequest.id == request_id)
    r = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not r:
        return HTMLResponse("Not found", status_code=404)
    matches = await match_listings(session, r, limit=15)
    settings = get_settings()
    api_base = settings.public_api_base.rstrip("/")
    return templates.TemplateResponse(
        "request_detail.html",
        {
            "request": request,
            "r": r,
            "matches": matches,
            "api_base": api_base,
        },
    )
