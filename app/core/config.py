from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from urllib.parse import quote


class Settings(BaseSettings):
    BOT_TOKEN: str
    ENCRYPTION_KEY: str
    SQLITE_DB_NAME: str = "revian.sqlite3"
    APP_TZ: str = "Europe/Moscow"
    LOG_FILE: str = "bot_logs.log"
    MESSAGE_RETENTION_DAYS: int = Field(default=3, ge=1)
    CLEANUP_HOUR: int = Field(default=19, ge=0, le=23)
    CLEANUP_MINUTE: int = Field(default=24, ge=0, le=59)
    RUN_CLEANUP_ON_START: bool = True
    POLLING_TASKS_LIMIT: int = Field(default=8, ge=1)
    MEDIA_DOWNLOAD_CONCURRENCY: int = Field(default=2, ge=1)
    MAX_MEDIA_SIZE_MB: int = Field(default=20, ge=1)
    TRIAL_PERIOD_HOURS: int = Field(default=48, ge=1)
    REFERRAL_BONUS_HOURS: int = Field(default=48, ge=1)
    TRIAL_NOTICE_COOLDOWN_MINUTES: int = Field(default=60, ge=1)
    TRIAL_SUPPORT_HANDLE: str = "@volchek903"
    TELEGRAM_STARTUP_TIMEOUT_SEC: int = Field(default=30, ge=1)
    TELEGRAM_STARTUP_RETRY_DELAY_SEC: int = Field(default=5, ge=1)
    TELEGRAM_STARTUP_RETRY_MAX_DELAY_SEC: int = Field(default=60, ge=1)
    TELEGRAM_PROXY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def DATABASE_URL(self) -> str:
        project_root = Path(__file__).resolve().parents[2]
        db_path = project_root / self.SQLITE_DB_NAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def TELEGRAM_PROXY_URL(self) -> str | None:
        if not self.TELEGRAM_PROXY:
            return None

        raw_proxy = self.TELEGRAM_PROXY.strip()
        if "://" in raw_proxy:
            return raw_proxy

        parts = raw_proxy.split(":")
        if len(parts) == 2:
            host, port = parts
            return f"http://{host}:{port}"

        if len(parts) == 4:
            host, port, username, password = parts
            safe_username = quote(username, safe="")
            safe_password = quote(password, safe="")
            return f"http://{safe_username}:{safe_password}@{host}:{port}"

        raise ValueError(
            "TELEGRAM_PROXY must be in URL format or host:port[:username:password]"
        )


settings = Settings()
