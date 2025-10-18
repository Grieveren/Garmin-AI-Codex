"""Central logging configuration for the Training Optimizer."""
from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path

from pydantic import ValidationError

from app.config import get_settings

_configured = False


def _default_config(log_dir: Path, level: str) -> dict:
    log_path = log_dir / "app.log"
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": fmt,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": level,
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": str(log_path),
                "encoding": "utf-8",
                "formatter": "standard",
                "level": level,
            },
        },
        "root": {
            "level": level,
            "handlers": ["console", "file"],
        },
    }


def configure_logging() -> None:
    """Configure application logging once per process."""

    global _configured
    if _configured:
        return

    try:
        settings = get_settings()
        log_dir = settings.log_dir
        level = settings.log_level
    except ValidationError:
        # Fallback for contexts (like certain tests) that inject required env vars later.
        log_dir = Path("logs")
        level = "INFO"
    log_dir.mkdir(parents=True, exist_ok=True)

    dictConfig(_default_config(log_dir, level))
    _configured = True
