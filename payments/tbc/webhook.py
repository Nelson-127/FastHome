"""FastAPI router: TBC webhook is a trigger only; confirmation uses TBC API + payment_flow."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.payment_flow import process_pay_id
from core.config import get_settings
from database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

_webhook_hits: dict[str, list[float]] = {}
_WEBHOOK_RL_WINDOW = 60.0
_WEBHOOK_RL_MAX = 120


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _check_webhook_rate(ip: str) -> None:
    import time

    now = time.monotonic()
    bucket = _webhook_hits.setdefault(ip, [])
    cutoff = now - _WEBHOOK_RL_WINDOW
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= _WEBHOOK_RL_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    bucket.append(now)


def _verify_signature_if_configured(body: bytes, signature_header: str | None) -> None:
    settings = get_settings()
    secret = settings.tbc_webhook_secret
    if not secret:
        return
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing signature")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header.strip().lower()):
        raise HTTPException(status_code=401, detail="Bad signature")


def _extract_pay_id(payload: dict[str, Any]) -> str | None:
    for key in ("payId", "pay_id", "paymentId", "id"):
        v = payload.get(key)
        if v:
            return str(v)
    return None


@router.post("/webhook")
async def tbc_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    settings = get_settings()
    if not settings.tbc_enabled:
        logger.info("TBC webhook ignored: TBC_ENABLED is false")
        return {"status": "tbc_disabled"}

    ip = _client_ip(request)
    _check_webhook_rate(ip)

    body = await request.body()
    sig = request.headers.get("x-tbc-signature") or request.headers.get("X-Signature")
    _verify_signature_if_configured(body, sig)

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError:
        payload = {}

    logger.info("TBC webhook received keys=%s", list(payload.keys()))

    pay_id = _extract_pay_id(payload)
    if not pay_id:
        logger.warning("TBC webhook: no pay_id")
        return {"status": "ignored"}

    return await process_pay_id(session, pay_id)
