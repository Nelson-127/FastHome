"""Parser for ss.ge rental listings (HTML structure may change — adjust selectors in production)."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from database.models import ListingSource
from parsing.base_parser import BaseParser

logger = logging.getLogger(__name__)

LIST_URL = "https://home.ss.ge/ru/%E1%83%98%E1%83%A0%E1%83%94%E1%83%9C%E1%83%93%E1%83%90%E1%83%91%E1%83%90-%E1%83%91%E1%83%98%E1%83%9C%E1%83%90%E1%83%91%E1%83%98?cityIdList=96&currencyId=1"


def _num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"([\d\s.,]+)", s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def _rooms_from_text(t: str) -> str | None:
    m = re.search(r"(\d+)\s*(?:room|ოთახ|комн)", t, re.I)
    if m:
        return m.group(1)
    m2 = re.search(r"\b(\d+)\s*\+", t)
    return m2.group(1) if m2 else None


class SsGeParser(BaseParser):
    async def parse(self) -> list[dict[str, Any]]:
        html = await self.fetch_text(LIST_URL)
        soup = BeautifulSoup(html, "html.parser")
        out: list[dict[str, Any]] = []
        # Typical card links — fallback: any /ru/ listing link
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if "/ru/" not in href or "ირენდება" not in href and "rent" not in href.lower():
                continue
            url = urljoin("https://home.ss.ge", href)
            title = (a.get_text(" ", strip=True) or "")[:500]
            if not title:
                continue
            price = _num(title)
            district = None
            # try parent text for location hints
            parent = a.parent
            if parent:
                blob = parent.get_text(" ", strip=True)
                district = blob.split(",")[-1].strip() if "," in blob else None
            rooms = _rooms_from_text(title)
            out.append(
                {
                    "source": ListingSource.ss_ge,
                    "url": url.split("?")[0],
                    "district": district,
                    "price": price,
                    "rooms": rooms,
                    "title": title,
                }
            )
        # Dedupe by URL in this batch
        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for row in out:
            u = row["url"]
            if u in seen:
                continue
            seen.add(u)
            uniq.append(row)
        logger.info("ss.ge parsed %s raw cards", len(uniq))
        return uniq[:200]
