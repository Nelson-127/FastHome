"""Low-level HTTP client for TBC tpay API (token, create payment, fetch payment)."""

from __future__ import annotations

import ssl
import time
from typing import Any

import aiohttp
import certifi

from core.config import Settings, get_settings

_token_cache: dict[str, Any] = {"value": None, "expires_at": 0}


def _ssl_connector() -> aiohttp.TCPConnector:
    ctx = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(ssl=ctx)


class TBCClient:
    """Thin async client; retries belong in service layer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()

    async def get_access_token(self) -> str:
        now = int(time.time())
        if _token_cache["value"] and now < int(_token_cache["expires_at"]) - 60:
            return str(_token_cache["value"])

        if not (self._s.tbc_apikey and self._s.tbc_client_id and self._s.tbc_client_secret):
            raise RuntimeError("TBC credentials missing (tbc_apikey, tbc_client_id, tbc_client_secret)")

        url = f"{self._s.tbc_api_base}{self._s.tbc_token_endpoint}"
        headers = {
            "apikey": self._s.tbc_apikey,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "client_id": self._s.tbc_client_id,
            "client_secret": self._s.tbc_client_secret,
        }

        async with aiohttp.ClientSession(connector=_ssl_connector()) as session:
            async with session.post(url, data=data, headers=headers) as resp:
                payload = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"TBC token error {resp.status}: {payload}")

                token = payload["access_token"]
                expires_in = int(payload.get("expires_in", 86400))
                _token_cache["value"] = token
                _token_cache["expires_at"] = now + expires_in
                return str(token)

    async def create_payment(
        self,
        amount_gel: float,
        return_url: str,
        callback_url: str,
        description: str,
        merchant_payment_id: str,
        language: str = "EN",
        expiration_minutes: int = 30,
    ) -> tuple[str, str]:
        token = await self.get_access_token()
        url = f"{self._s.tbc_api_base}{self._s.tbc_payments_endpoint}"
        headers = {
            "apikey": self._s.tbc_apikey,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "amount": {"currency": "GEL", "total": amount_gel},
            "returnurl": return_url,
            "callbackUrl": callback_url,
            "description": description[:30],
            "merchantPaymentId": merchant_payment_id,
            "language": language,
            "expirationMinutes": expiration_minutes,
        }

        async with aiohttp.ClientSession(connector=_ssl_connector()) as session:
            async with session.post(url, json=body, headers=headers) as resp:
                payload = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"TBC create payment error {resp.status}: {payload}")

                pay_id = str(payload["payId"])
                links = payload.get("links", []) or []
                approval_url = None
                for link in links:
                    if link.get("rel") == "approval_url":
                        approval_url = link.get("uri")
                        break
                if not approval_url:
                    raise RuntimeError(f"TBC response has no approval_url: {payload}")
                return pay_id, str(approval_url)

    async def get_payment(self, pay_id: str) -> dict[str, Any]:
        """Full payment object from TBC (source of truth for verify)."""
        token = await self.get_access_token()
        url = f"{self._s.tbc_api_base}{self._s.tbc_payments_endpoint}/{pay_id}"
        headers = {
            "apikey": self._s.tbc_apikey,
            "Authorization": f"Bearer {token}",
        }
        async with aiohttp.ClientSession(connector=_ssl_connector()) as session:
            async with session.get(url, headers=headers) as resp:
                payload = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"TBC get payment error {resp.status}: {payload}")
                if not isinstance(payload, dict):
                    raise RuntimeError(f"TBC get payment invalid JSON: {payload}")
                return payload
