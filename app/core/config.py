from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    ENCRYPTION_KEY: str

    class Config:
        env_file = ".env"


settings = Settings()
