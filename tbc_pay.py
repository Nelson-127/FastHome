import aiohttp
import time
import ssl
import certifi

from config import (
    TBC_API_BASE,
    TBC_TOKEN_ENDPOINT,
    TBC_PAYMENTS_ENDPOINT,
    TBC_APIKEY,
    TBC_CLIENT_ID,
    TBC_CLIENT_SECRET,
)

_token_cache: dict = {"value": None, "expires_at": 0}


def _ssl_connector() -> aiohttp.TCPConnector:
    # Используем CA bundle от certifi (решает 90% проблем с SSL на macOS/в venv)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(ssl=ssl_context)


async def get_access_token() -> str:
    now = int(time.time())
    if _token_cache["value"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["value"]

    if not (TBC_APIKEY and TBC_CLIENT_ID and TBC_CLIENT_SECRET):
        raise RuntimeError("TBC credentials are not set (TBC_APIKEY/TBC_CLIENT_ID/TBC_CLIENT_SECRET)")

    url = f"{TBC_API_BASE}{TBC_TOKEN_ENDPOINT}"
    headers = {
        "apikey": TBC_APIKEY,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "client_id": TBC_CLIENT_ID,
        "client_secret": TBC_CLIENT_SECRET,
    }

    async with aiohttp.ClientSession(connector=_ssl_connector()) as session:
        async with session.post(url, data=data, headers=headers) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"TBC token error {resp.status}: {payload}")

            token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 86400))
            _token_cache["value"] = token
            _token_cache["expires_at"] = now + expires_in
            return token


async def create_payment(
    amount_gel: float,
    return_url: str,
    callback_url: str,
    description: str,
    merchant_payment_id: str,
    language: str = "EN",
    expiration_minutes: int = 12,
) -> tuple[str, str]:
    """
    Возвращает (payId, approval_url)
    """
    token = await get_access_token()
    url = f"{TBC_API_BASE}{TBC_PAYMENTS_ENDPOINT}"
    headers = {
        "apikey": TBC_APIKEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
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
            payload = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"TBC create payment error {resp.status}: {payload}")

            pay_id = payload["payId"]
            links = payload.get("links", []) or []
            approval_url = None
            for l in links:
                if l.get("rel") == "approval_url":
                    approval_url = l.get("uri")
                    break

            if not approval_url:
                raise RuntimeError(f"TBC response has no approval_url: {payload}")

            return pay_id, approval_url


async def get_payment_status(pay_id: str) -> str:
    token = await get_access_token()
    url = f"{TBC_API_BASE}{TBC_PAYMENTS_ENDPOINT}/{pay_id}"
    headers = {
        "apikey": TBC_APIKEY,
        "Authorization": f"Bearer {token}",
    }

    async with aiohttp.ClientSession(connector=_ssl_connector()) as session:
        async with session.get(url, headers=headers) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"TBC get payment error {resp.status}: {payload}")
            return payload.get("status", "")