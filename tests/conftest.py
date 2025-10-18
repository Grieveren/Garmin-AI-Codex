"""Pytest configuration for global test fixtures."""
from __future__ import annotations

import os


# Ensure SECRET_KEY is populated before any application modules import settings.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
