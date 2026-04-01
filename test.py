from aiogram import Bot
import asyncio
from config import BOT_TOKEN
from config import ADMIN_IDS

async def main():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(ADMIN_IDS, "Привет, это тестовое сообщение")

asyncio.run(main())