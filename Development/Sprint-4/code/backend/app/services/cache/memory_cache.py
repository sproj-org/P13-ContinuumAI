"""In-memory TTL cache implementation."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class InMemoryTTLCache:
    def __init__(self) -> None:
        self._items: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            if item.expires_at < now:
                self._items.pop(key, None)
                return None
            return copy.deepcopy(item.value)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._items[key] = _CacheEntry(value=copy.deepcopy(value), expires_at=expires_at)
