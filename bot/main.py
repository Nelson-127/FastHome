"""Run Telegram bot (polling)."""

from __future__ import annotations

import asyncio
import logging
import os

# Prevent pydantic entry-point plugin discovery from hanging in broken environments.
os.environ["PYDANTIC_DISABLE_PLUGINS"] = "__all__"

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import admin as admin_handlers
from bot.handlers import user as user_handlers
from bot.middlewares.throttle import UserThrottleMiddleware
from core.config import get_settings
from core.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    # Long polling конфликтует с webhook: снимаем webhook при старте.
    # Ошибка «only one bot instance» также бывает, если второй процесс с тем же токеном — его нужно остановить вручную.
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Telegram webhook cleared (using long polling)")

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(UserThrottleMiddleware())
    dp.callback_query.middleware(UserThrottleMiddleware())
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    logger.info("Bot polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
