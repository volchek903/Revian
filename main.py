from loguru import logger
import sys
import os
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError

from app.core.config import settings
from app.core.db import init_db
from app.handlers.chats import router as router_chats
from app.handlers.bots import router as router_bots
from app.repository.message import crud_message  # метод delete_messages_older_than(days=30)

# --- Bot / Dispatcher ---
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router_bots)
dp.include_router(router_chats)

# --- Таймзона и планировщик ---
APP_TZ = os.getenv("APP_TZ") or getattr(settings, "APP_TZ", "Europe/Moscow")
TZINFO = ZoneInfo(APP_TZ)


async def _run_cleanup():
    try:
        deleted = await crud_message.delete_messages_older_than(days=30)
        logger.info(f"🧹 Purge: deleted {deleted} messages older than 30 days")
    except Exception:
        logger.exception("❌ Purge failed")


async def _daily_cleanup_worker(hour: int = 19, minute: int = 24, run_on_start: bool = False):
    # Выполнить сразу при старте (по желанию)
    if run_on_start:
        await _run_cleanup()

    while True:
        now = datetime.now(TZINFO)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run < now:  # если время уже прошло — переносим на завтра
            next_run += timedelta(days=1)

        sleep_s = max(0, (next_run - now).total_seconds())
        logger.info(f"⏰ Cleanup scheduled: now={now}, next_run={next_run}, tz={APP_TZ}, sleep={int(sleep_s)}s")
        await asyncio.sleep(sleep_s)

        await _run_cleanup()


# --- Startup / Shutdown хуки ---
async def _on_startup():
    await init_db()
    me = await bot.get_me()
    logger.info(
        f"🤖 Bot started: {me.full_name} (@{me.username}), id={me.id}"
    )
    # Снимаем webhook перед polling, чтобы не было конфликта getUpdates
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем ежедневный воркер на 19:24 по выбранной таймзоне
    asyncio.create_task(_daily_cleanup_worker(hour=0, minute=0, run_on_start=False))
    logger.info(f"✅ Scheduler: daily cleanup at 19:24 ({APP_TZ}). Webhook disabled for polling.")


dp.startup.register(_on_startup)

# --- Entry point ---
if __name__ == "__main__":
    logger.add("bot_logs.log", rotation="1 week", retention="30 days", compression="zip")
    logger.info("🚀 Starting bot...")

    try:
        dp.run_polling(bot)
    except TelegramConflictError:
        logger.error("❌ Conflict: другой процесс уже вызывает getUpdates этим токеном. Останови его или удали webhook.")
        sys.exit(2)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске бота: {e}")
        sys.exit(1)
