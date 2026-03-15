import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers.start import router as start_router
from handlers.menu import router as menu_router
from handlers.game import router as game_router

async def main():
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing. Add it to environment variables.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(game_router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())