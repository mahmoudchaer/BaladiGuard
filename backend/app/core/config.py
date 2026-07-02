from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:8081,http://localhost:19006"


@lru_cache
def get_settings() -> Settings:
    return Settings()
