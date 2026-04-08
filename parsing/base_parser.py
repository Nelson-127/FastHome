"""Async HTTP fetch with retries, rate limiting, and rotating User-Agents."""

from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

import aiohttp
import certifi
import ssl

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


def _ssl_connector() -> aiohttp.TCPConnector:
    ctx = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(ssl=ctx)


@dataclass
class RateLimiter:
    """Simple token bucket per host."""

    max_per_minute: int = 30
    _times: deque[float] = field(default_factory=deque)

    async def acquire(self) -> None:
        now = monotonic()
        window = 60.0
        while self._times and now - self._times[0] > window:
            self._times.popleft()
        if len(self._times) >= self.max_per_minute:
            sleep_for = window - (now - self._times[0])
            await asyncio.sleep(max(sleep_for, 0.1))
            return await self.acquire()
        self._times.append(monotonic())


class BaseParser:
    def __init__(self, *, max_retries: int = 4, timeout_sec: float = 25.0) -> None:
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self._limiter = RateLimiter()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ka;q=0.8,ru;q=0.7",
        }

    async def fetch_text(self, url: str) -> str:
        await self._limiter.acquire()
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
                async with aiohttp.ClientSession(connector=_ssl_connector(), timeout=timeout) as session:
                    async with session.get(url, headers=self._headers(), allow_redirects=True) as resp:
                        if resp.status >= 400:
                            raise RuntimeError(f"HTTP {resp.status} for {url}")
                        return await resp.text()
            except Exception as e:
                last_err = e
                delay = 0.5 * (2 ** (attempt - 1))
                logger.warning("fetch retry %s/%s %s: %s", attempt, self.max_retries, url, e)
                await asyncio.sleep(delay)
        assert last_err is not None
        raise last_err

    async def parse(self) -> list[dict[str, Any]]:
        raise NotImplementedError
