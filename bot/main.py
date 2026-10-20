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

    # Регистрация системных команд в Telegram (кнопка Menu в левом нижнем углу)
    commands = [
        BotCommand(command="start", description="Перезапустить Ателье и приветствие"),
        BotCommand(command="club", description="Условия резидентуры и подписка (20 мест)"),
        BotCommand(command="services", description="Сетка услуг и списание Atelier Credits"),
        BotCommand(command="status", description="Баланс кредитов и статус резидента"),
        BotCommand(command="clear", description="Очистить контекст диалога"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Системное меню команд Telegram успешно зарегистрировано.")
    except Exception as e:
        logging.error(f"Ошибка регистрации команд меню: {e}")

    logging.info('Элин запускается...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
