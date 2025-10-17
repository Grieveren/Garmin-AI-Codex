"""Application configuration management."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings derived from environment variables."""

    garmin_email: str
    garmin_password: str
    anthropic_api_key: str
    database_url: str = "sqlite:///./data/training_data.db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me"
    debug: bool = True
    garmin_token_store: str | None = ".garmin_tokens"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance so it can be reused across the app."""

    return Settings()
