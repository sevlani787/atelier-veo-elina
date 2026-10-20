import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

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

    # Universal Telegram commands in English for international luxury founders
    commands = [
        BotCommand(command="start", description="Restart Atelier & Director greeting"),
        BotCommand(command="club", description="Private Residency terms & 20-seat quota"),
        BotCommand(command="services", description="Production rates & Atelier Credits menu"),
        BotCommand(command="status", description="Your Atelier Credits balance & status"),
        BotCommand(command="clear", description="Clear dialogue memory"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Telegram commands menu successfully registered in English.")
    except Exception as e:
        logging.error(f"Error registering menu commands: {e}")

    logging.info('Элин запускается...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
