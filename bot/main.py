import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import config
from bot.handlers.messages import router as messages_router
from bot.handlers.payments import router as payments_router
from bot.services.database import db

logging.basicConfig(level=logging.INFO)


async def main():
    # Initialize database
    await db.init()

    bot = Bot(
        token=config.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(messages_router)
    dp.include_router(payments_router)

    logging.info('Элин запускается...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())