"""Per-user simple rate limiting (in-memory)."""

from __future__ import annotations

import time
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.config import get_settings


class UserThrottleMiddleware(BaseMiddleware):
    def __init__(self, *, min_interval_sec: float = 0.35) -> None:
        self.min_interval_sec = min_interval_sec
        self._last: dict[int, float] = defaultdict(float)

    async def __call__(self, handler, event: TelegramObject, data: dict):
        settings = get_settings()
        if not settings.admin_id_list:
            pass
        uid = None
        if hasattr(event, "from_user") and event.from_user:
            uid = event.from_user.id
        if uid is None:
            return await handler(event, data)
        now = time.monotonic()
        last = self._last[uid]
        if now - last < self.min_interval_sec:
            return None
        self._last[uid] = now
        return await handler(event, data)
