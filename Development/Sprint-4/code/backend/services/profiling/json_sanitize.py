"""Utilities for JSON-safe data conversion."""

from __future__ import annotations

import math
from typing import Any

NON_FINITE_STRINGS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan"}


def _is_non_finite_string(value: str) -> bool:
    return value.strip().lower() in NON_FINITE_STRINGS


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively replace non-finite float values with None.
    """
    if isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]

    if isinstance(obj, tuple):
        return tuple(sanitize_for_json(item) for item in obj)

    if isinstance(obj, float):
        return float(obj) if math.isfinite(obj) else None

    if isinstance(obj, str):
        return None if _is_non_finite_string(obj) else obj

    if isinstance(obj, int) or obj is None:
        return obj

    return obj
