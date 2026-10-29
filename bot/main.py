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
from bot.services.subscription_manager import subscription_watchdog

logging.basicConfig(level=logging.INFO)


async def main():
    # Initialize database
    await db.init()

    bot_session = None
    if config.telegram_api_server:
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        server = TelegramAPIServer.from_base(config.telegram_api_server, is_local=True)
        bot_session = AiohttpSession(api=server)
        logging.info(f"Using local Telegram Bot API server at {config.telegram_api_server} (is_local=True)")

    bot = Bot(
        token=config.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=bot_session
    )

    dp = Dispatcher()
    dp.include_router(messages_router)
    dp.include_router(payments_router)

    # Universal Telegram commands in English for international luxury founders
    commands = [
        BotCommand(command="start", description="Restart Atelier & Director greeting"),
        BotCommand(command="prompt", description="Dual-Layer Cinematic Prompt (20 Cr)"),
        BotCommand(command="qa", description="Visual QA & Prompt Doctor (25 Cr)"),
        BotCommand(command="audit", description="Website & Instagram Teardown (50 Cr)"),
        BotCommand(command="muse", description="Virtual Muse Architecture (100 Cr)"),
        BotCommand(command="dna", description="Living Brand DNA Sovereign Vault (0 Cr)"),
        BotCommand(command="status", description="Your Atelier Credits balance & residency"),
        BotCommand(command="topup", description="Booster top-up packs (+300, +700, +1500)"),
        BotCommand(command="club", description="Private Residency terms & 20-seat quota"),
        BotCommand(command="help", description="Guide to Elina's 5 Directorial Modules"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Telegram commands menu successfully registered in English.")
    except Exception as e:
        logging.error(f"Error registering menu commands: {e}")

    logging.info('Элин запускается...')
    watchdog_task = asyncio.create_task(subscription_watchdog(bot))
    try:
        await dp.start_polling(bot)
    finally:
        watchdog_task.cancel()


if __name__ == '__main__':
    asyncio.run(main())
