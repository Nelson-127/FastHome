"""HTTP client for backend API (no DB access)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    s = get_settings()
    h: dict[str, str] = {}
    if s.internal_api_key:
        h["X-Internal-Key"] = s.internal_api_key
    return h


async def post_request(payload: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/requests"
    async with httpx.AsyncClient(timeout=40.0) as client:
        r = await client.post(url, json=payload, headers=_headers())
        r.raise_for_status()
        return r.json()


async def get_request(request_id: int, telegram_id: int) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/requests/{request_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params={"telegram_id": telegram_id}, headers=_headers())
        r.raise_for_status()
        return r.json()


async def create_payment(request_id: int, telegram_id: int) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/payments/create"
    body = {"request_id": request_id, "telegram_id": telegram_id}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body, headers=_headers())
        r.raise_for_status()
        return r.json()
