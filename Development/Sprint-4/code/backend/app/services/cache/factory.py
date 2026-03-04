"""Cache backend factory."""

from __future__ import annotations

from app.services.cache.cache import CacheBackend
from app.services.cache.memory_cache import InMemoryTTLCache

_MEMORY_CACHE = InMemoryTTLCache()


def get_cache() -> CacheBackend:
    return _MEMORY_CACHE
