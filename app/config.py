"""Application configuration management."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings derived from environment variables."""

    garmin_email: str
    garmin_password: str
    anthropic_api_key: str

    secret_key: str

    database_url: str = Field(
        default="sqlite:///./data/training_data.db",
        description="SQLAlchemy-compatible database URL.",
    )
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)

    debug: bool = Field(default=False)
    garmin_token_store: str | None = Field(
        default=".garmin_tokens",
        description="Path to cached Garmin tokens (or null to disable cache).",
    )

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("logs"))
    scheduler_hour: int = Field(default=8, ge=0, le=23)
    scheduler_minute: int = Field(default=0, ge=0, le=59)
    scheduler_lock_file: Path = Field(default=Path(".scheduler.lock"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Ensure the secret key is not left as a placeholder."""

        if value.strip().lower() in {"", "change-me", "changeme"}:
            raise ValueError(
                "SECRET_KEY is required. Update your .env file with a strong secret before running the app."
            )
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = value.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {', '.join(sorted(valid))}")
        return upper


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance so it can be reused across the app."""

    settings = Settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
