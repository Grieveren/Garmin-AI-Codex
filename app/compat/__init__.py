"""Compatibility helpers loaded early to patch third-party behavior."""

from .pydantic_eval_patch import ensure_pydantic_eval_patch

ensure_pydantic_eval_patch()

__all__ = ["ensure_pydantic_eval_patch"]
