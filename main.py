from loguru import logger
import sys
from aiogram import Dispatcher
from app.handlers.chats import router as router_chats
from app.handlers.bots import router as router_bots
from app.core.config import settings
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

bot = Bot(
    token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

dp.include_router(router_bots)
dp.include_router(router_chats)

if __name__ == "__main__":
    logger.add(
        "bot_logs.log", rotation="1 week", retention="30 days", compression="zip"
    )
    logger.info("🚀 Starting bot...")

    try:
        dp.run_polling(bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске бота: {e}")
        sys.exit(1)
