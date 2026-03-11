from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ENCRYPTION_KEY: str
    SQLITE_DB_NAME: str = "revian.sqlite3"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def DATABASE_URL(self) -> str:
        project_root = Path(__file__).resolve().parents[2]
        db_path = project_root / self.SQLITE_DB_NAME
        return f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
