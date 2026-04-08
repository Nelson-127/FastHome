"""Admin operations via backend REST (Basic auth) — bot has no DB."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)


def _auth() -> tuple[str, str]:
    s = get_settings()
    return (s.admin_username, s.admin_password)


async def admin_list_requests(*, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/admin/requests"
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    async with httpx.AsyncClient(timeout=40.0, auth=_auth()) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def admin_patch_request(request_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/admin/requests/{request_id}"
    async with httpx.AsyncClient(timeout=40.0, auth=_auth()) as client:
        r = await client.patch(url, json=payload)
        r.raise_for_status()
        return r.json()


async def admin_get_request(request_id: int) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/admin/requests/{request_id}"
    async with httpx.AsyncClient(timeout=40.0, auth=_auth()) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def admin_get_matches(request_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    s = get_settings()
    url = f"{s.backend_base_url.rstrip('/')}/admin/requests/{request_id}/matches"
    async with httpx.AsyncClient(timeout=40.0, auth=_auth()) as client:
        r = await client.get(url, params={"limit": limit})
        r.raise_for_status()
        return r.json()
