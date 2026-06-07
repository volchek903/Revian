from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ENCRYPTION_KEY: str
    SQLITE_DB_NAME: str = "revian.sqlite3"
    APP_TZ: str = "Europe/Moscow"
    LOG_FILE: str = "bot_logs.log"
    CLEANUP_HOUR: int = Field(default=19, ge=0, le=23)
    CLEANUP_MINUTE: int = Field(default=24, ge=0, le=59)
    RUN_CLEANUP_ON_START: bool = False
    POLLING_TASKS_LIMIT: int = Field(default=8, ge=1)
    MEDIA_DOWNLOAD_CONCURRENCY: int = Field(default=2, ge=1)
    MAX_MEDIA_SIZE_MB: int = Field(default=20, ge=1)
    TELEGRAM_STARTUP_TIMEOUT_SEC: int = Field(default=30, ge=1)
    TELEGRAM_STARTUP_RETRY_DELAY_SEC: int = Field(default=5, ge=1)
    TELEGRAM_STARTUP_RETRY_MAX_DELAY_SEC: int = Field(default=60, ge=1)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def DATABASE_URL(self) -> str:
        project_root = Path(__file__).resolve().parents[2]
        db_path = project_root / self.SQLITE_DB_NAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
