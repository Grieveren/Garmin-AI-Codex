"""Work around pydantic 2.12 strict annotation evaluation quirks.

garth>=0.5.17 defines ``HRVData.list`` as a classmethod while also annotating
``hrv_readings: list[HRVReading]``. When pydantic evaluates the dataclass typing
information it uses the class namespace, so ``list`` resolves to that method
instead of the builtin and raises ``TypeError: 'classmethod' object is not
subscriptable``. We patch pydantic's evaluation helper to restore builtin
types when they are shadowed by class attributes.
"""
from __future__ import annotations

import builtins
from typing import Any, Mapping

from pydantic._internal import _typing_extra as typing_extra

_BUILTIN_NAMES = ("list", "dict", "set", "tuple")
_PATCHED = False


def _coerce_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if mapping is None:
        return {}
    if isinstance(mapping, dict):
        return mapping
    return dict(mapping)


def ensure_pydantic_eval_patch() -> None:
    """Install the eval_type_backport shim once."""
    global _PATCHED
    if _PATCHED:
        return

    original = typing_extra.eval_type_backport

    def _patched_eval_type_backport(
        value: Any,
        globalns: Mapping[str, Any] | None = None,
        localns: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            return original(value, globalns, localns)
        except TypeError:
            # Retry with builtin collection types restored if they were shadowed.
            shadowed = False
            coerced_locals = _coerce_mapping(localns)
            for name in _BUILTIN_NAMES:
                candidate = coerced_locals.get(name)
                builtin_value = getattr(builtins, name, None)
                if candidate is not None and candidate is not builtin_value:
                    if isinstance(candidate, (classmethod, staticmethod)) or callable(candidate):
                        coerced_locals[name] = builtin_value
                        shadowed = True
            if shadowed:
                return original(value, globalns, coerced_locals)
            raise

    typing_extra.eval_type_backport = _patched_eval_type_backport  # type: ignore[assignment]
    _PATCHED = True

