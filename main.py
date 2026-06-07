from loguru import logger
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError

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
APP_TZ = settings.APP_TZ
TZINFO = ZoneInfo(APP_TZ)
LOG_FILE = settings.LOG_FILE
POLLING_TASKS_LIMIT = settings.POLLING_TASKS_LIMIT
TELEGRAM_STARTUP_TIMEOUT_SEC = settings.TELEGRAM_STARTUP_TIMEOUT_SEC
TELEGRAM_STARTUP_RETRY_DELAY_SEC = settings.TELEGRAM_STARTUP_RETRY_DELAY_SEC
TELEGRAM_STARTUP_RETRY_MAX_DELAY_SEC = settings.TELEGRAM_STARTUP_RETRY_MAX_DELAY_SEC

cleanup_task: asyncio.Task | None = None


def _ensure_runtime_dirs() -> None:
    log_path = Path(LOG_FILE)
    if log_path.parent != Path("."):
        log_path.parent.mkdir(parents=True, exist_ok=True)


async def _run_cleanup():
    try:
        deleted = await crud_message.delete_messages_older_than(days=30)
        logger.info(f"🧹 Purge: deleted {deleted} messages older than 30 days")
    except Exception:
        logger.exception("❌ Purge failed")


async def _call_telegram_api_with_retry(action_name: str, func, **kwargs):
    delay = TELEGRAM_STARTUP_RETRY_DELAY_SEC

    while True:
        try:
            return await func(
                request_timeout=TELEGRAM_STARTUP_TIMEOUT_SEC,
                **kwargs,
            )
        except TelegramNetworkError as e:
            logger.warning(
                f"🌐 Telegram API timeout during {action_name}: {e}. "
                f"Retry in {delay}s"
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, TELEGRAM_STARTUP_RETRY_MAX_DELAY_SEC)


async def _daily_cleanup_worker(hour: int = 19, minute: int = 24, run_on_start: bool = False):
    if run_on_start:
        await _run_cleanup()

    while True:
        now = datetime.now(TZINFO)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run < now:  # если время уже прошло — переносим на завтра
            next_run += timedelta(days=1)

        sleep_s = max(0, (next_run - now).total_seconds())
        logger.info(f"⏰ Cleanup scheduled: now={now}, next_run={next_run}, tz={APP_TZ}, sleep={int(sleep_s)}s")
        try:
            await asyncio.sleep(sleep_s)
        except asyncio.CancelledError:
            logger.info("🛑 Cleanup worker stopped")
            raise

        await _run_cleanup()


# --- Startup / Shutdown хуки ---
async def _on_startup():
    global cleanup_task

    await init_db()
    me = await _call_telegram_api_with_retry("get_me", bot.get_me)
    logger.info(
        f"🤖 Bot started: {me.full_name} (@{me.username}), id={me.id}"
    )
    await _call_telegram_api_with_retry(
        "delete_webhook",
        bot.delete_webhook,
        drop_pending_updates=True,
    )
    cleanup_task = asyncio.create_task(
        _daily_cleanup_worker(
            hour=settings.CLEANUP_HOUR,
            minute=settings.CLEANUP_MINUTE,
            run_on_start=settings.RUN_CLEANUP_ON_START,
        ),
        name="daily-cleanup-worker",
    )
    logger.info(
        "✅ Scheduler: daily cleanup at "
        f"{settings.CLEANUP_HOUR:02d}:{settings.CLEANUP_MINUTE:02d} ({APP_TZ}). "
        f"Webhook disabled for polling. tasks_limit={POLLING_TASKS_LIMIT}"
    )


async def _on_shutdown():
    global cleanup_task

    if cleanup_task is None:
        return

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    finally:
        cleanup_task = None
    logger.info("👋 Bot shutdown complete")


dp.startup.register(_on_startup)
dp.shutdown.register(_on_shutdown)


def _close_bot_session() -> None:
    try:
        asyncio.run(bot.session.close())
    except Exception:
        logger.debug("Bot session close skipped")

# --- Entry point ---
if __name__ == "__main__":
    _ensure_runtime_dirs()
    logger.add(
        LOG_FILE,
        rotation="1 week",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.info("🚀 Starting bot...")

    try:
        dp.run_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            tasks_concurrency_limit=POLLING_TASKS_LIMIT,
        )
    except TelegramConflictError:
        logger.error("❌ Conflict: другой процесс уже вызывает getUpdates этим токеном. Останови его или удали webhook.")
        _close_bot_session()
        sys.exit(2)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске бота: {e}")
        _close_bot_session()
        sys.exit(1)
