import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/inventory_db"
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql://user:password@localhost:5432/inventory_db"
    )

    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    ENVIRONMENT: str = Field(default="prod")

    RAKUTEN_DEFAULT_SERVICE_SECRET: str = Field(default="")
    RAKUTEN_DEFAULT_LICENSE_KEY: str = Field("")
    RAKUTEN_PROXY: Optional[str] = Field(default=None)

    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.lower() == "test"

    @property
    def db_name(self) -> str:
        if self.is_test:
            return "inventory_db_test"
        return "inventory_db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
