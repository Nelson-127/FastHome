"""Payment creation (TBC) — called by bot after request exists."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_internal_key
from backend.schemas.requests import PaymentCreateBody, PaymentCreateResponse
from backend.services.payment_service import create_tbc_payment_for_request
from database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    body: PaymentCreateBody,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_internal_key),
) -> PaymentCreateResponse:
    try:
        pay_id, approval_url, amount = await create_tbc_payment_for_request(
            session,
            request_id=body.request_id,
            telegram_id=body.telegram_id,
        )
    except ValueError as e:
        code = str(e)
        if code == "request_not_found_or_forbidden":
            raise HTTPException(status_code=404, detail="Request not found")
        if code == "payment_already_pending":
            raise HTTPException(status_code=409, detail="Payment already pending; use stored link")
        if code == "tbc_not_configured":
            raise HTTPException(status_code=503, detail="TBC payment is not configured on server")
        if code == "tbc_disabled":
            raise HTTPException(status_code=503, detail="TBC card payment is disabled (set TBC_ENABLED=true when ready)")
        raise HTTPException(status_code=400, detail=code)
    return PaymentCreateResponse(pay_id=pay_id, approval_url=approval_url, amount_gel=amount)
