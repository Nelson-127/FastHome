from __future__ import annotations

import logging
from typing import Any

import httpx

from database.models import ListingSource
from parsing.base_parser import BaseParser

logger = logging.getLogger(__name__)

API_URL = "https://api-statements.tnet.ge/v1/statements?is_super_vip=1&per_page=50&is_home_cache=1"


class MyHomeParser(BaseParser):
    async def parse(self) -> list[dict[str, Any]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.myhome.ge",
            "Referer": "https://www.myhome.ge/",
            "X-Website-Key": "myhome",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(API_URL, headers=headers)

        if resp.status_code != 200:
            print(resp.text)  # важно для дебага
            raise RuntimeError(f"HTTP {resp.status_code}")

        data = resp.json()
        items = data.get("data", {}).get("data", [])

        result = []

        for item in items:
            try:
                price = None

                if "price" in item and "1" in item["price"]:
                    price = float(item["price"]["1"]["price_total"])

                url = f"https://www.myhome.ge/pr/{item.get('id')}"

                result.append(
                    {
                        "source": ListingSource.myhome_ge,
                        "url": url,
                        "district": item.get("district"),
                        "price": price,
                        "rooms": None,
                        "title": item.get("street") or "No title",
                        "raw_meta": item,
                    }
                )
            except Exception:
                logger.exception("Failed to parse item")

        logger.info("myhome API parsed %s items", len(result))
        print(f"✅ MyHomeParser parsed: {len(result)} items")

        return result