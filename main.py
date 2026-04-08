"""Legacy entrypoint: запуск бота (UI). API: `uvicorn backend.main:app`."""

from __future__ import annotations

import asyncio
import os

# Workaround for slow/broken external pydantic plugin discovery in some local envs.
os.environ["PYDANTIC_DISABLE_PLUGINS"] = "__all__"

from bot.main import main as bot_main


if __name__ == "__main__":
    asyncio.run(bot_main())
