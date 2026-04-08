"""Telegram notifications from backend (payment success, admin alerts)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from core.config import get_settings
from database.models import User

logger = logging.getLogger(__name__)


async def _tg_api(method: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            body = await resp.json()
            if not body.get("ok"):
                logger.error("Telegram API error %s: %s", method, body)


async def send_user_message(telegram_id: int, text: str, parse_mode: str = "HTML") -> None:
    await _tg_api(
        "sendMessage",
        {"chat_id": telegram_id, "text": text, "parse_mode": parse_mode},
    )


async def notify_admins(text: str) -> None:
    settings = get_settings()
    for aid in settings.admin_id_list:
        try:
            await send_user_message(aid, text)
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", aid, e)


async def notify_payment_success_for_user(
    user: User,
    request_id: int,
    *,
    max_variants: int,
    hours: int,
) -> None:
    """User-facing message after verified TBC payment."""
    lang = (user.language or "ru").lower()
    from translations.service import t

    text = t(
        "user_paid_success",
        lang,
        max_v=max_variants,
        hours=hours,
    )
    try:
        await send_user_message(user.telegram_id, text)
    except Exception as e:
        logger.exception("Notify user payment failed: %s", e)


async def notify_admins_new_request(request_id: int, district: str, username: str | None) -> None:
    u = f"@{username}" if username else "—"
    await notify_admins(
        f"🆕 <b>Новая заявка #{request_id}</b>\n"
        f"Юзер: {u}\n"
        f"Район: {district}",
    )

from sqlalchemy import select
from database.models import SentListing


async def notify_matches_for_user(session, user, matches):
    if not matches:
        return

    # 1. Проверяем что уже отправляли
    result = await session.execute(
        select(SentListing).where(
            SentListing.user_id == user.id,
            SentListing.listing_id.in_([m.id for m in matches])
        )
    )

    sent_ids = {x.listing_id for x in result.scalars()}

    # 2. Фильтруем новые
    new_matches = [m for m in matches if m.id not in sent_ids]

    if not new_matches:
        return

    # 3. Ограничение (чтобы не спамить)
    new_matches = new_matches[:5]

    # 4. Отправка
    for m in new_matches:
        text = f"💰 {m.price or '?'}$\n{m.title or 'Без названия'}"

        payload = {
            "chat_id": user.telegram_id,
            "photo": getattr(m, "image_url", None) or "https://via.placeholder.com/300",
            "caption": text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "Открыть", "url": m.url}]
                ]
            }
        }

        await _tg_api("sendPhoto", payload)

        # 5. Запоминаем что отправили
        session.add(SentListing(user_id=user.id, listing_id=m.id))

    await session.commit()