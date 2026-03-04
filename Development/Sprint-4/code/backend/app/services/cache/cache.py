"""Cache protocol used by chart preview execution."""

from __future__ import annotations

from typing import Any, Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None:
        ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        ...
