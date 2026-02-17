"""
Redis cache module for ChartSpec query caching.

Provides caching functionality to reduce database load and improve
response times for repeated queries. Uses Redis as the backing store.

Cache Strategy:
- Key: MD5 hash of normalized ChartSpec (excluding chart.type and version)
- Value: AggregateResponse JSON (columns + rows)
- TTL: Configurable (default 5 minutes)

Error Handling Philosophy:
- Cache failures are logged but don't crash the application
- On Redis errors, operations return None/False and application continues
- Cache is an optimization, not a critical dependency
"""

import json
import hashlib
import logging
from typing import Optional, Any

import redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    Get or create Redis client singleton.

    Uses lazy initialization with connection pooling.
    Reads configuration from Settings.

    Returns:
        Redis client instance

    Raises:
        RedisError: If connection fails (should be caught by callers)
    """
    global _redis_client

    if _redis_client is None:
        settings = get_settings()

        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            _redis_client.ping()
            logger.info(f"Redis connected successfully: {settings.REDIS_URL}")

        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return _redis_client


def ping_redis() -> bool:
    """
    Health check for Redis connection.

    Used by health endpoints to verify Redis availability.
    Safe to call - doesn't raise exceptions.

    Returns:
        True if Redis is reachable, False otherwise
    """
    try:
        client = get_redis()
        client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


def get_cache_key(prefix: str, data: dict) -> str:
    """
    Generate deterministic cache key from data dictionary.

    Process:
    1. Serialize dict to JSON (sorted keys for consistency)
    2. Compute MD5 hash of JSON string
    3. Return formatted key: "{prefix}:{hash}"

    Args:
        prefix: Namespace prefix (e.g., "chartspec")
        data: Dictionary to hash (should be normalized)

    Returns:
        Cache key string (e.g., "chartspec:a1b2c3d4...")
    """
    # Canonicalize by sorting keys
    canonical_json = json.dumps(data, sort_keys=True, ensure_ascii=False)

    # Generate hash
    hash_value = hashlib.md5(canonical_json.encode("utf-8")).hexdigest()

    # Format key
    key = f"{prefix}:{hash_value}"

    logger.debug(f"Generated cache key: {key}")
    return key


def get_cached(key: str) -> Optional[dict]:
    """
    Retrieve cached data by key.

    Args:
        key: Cache key to lookup

    Returns:
        Cached dictionary if exists, None otherwise

    Note:
        Returns None on Redis errors (fail gracefully)
    """
    settings = get_settings()

    # If caching is disabled, return None
    if not settings.CACHE_ENABLED:
        return None

    try:
        client = get_redis()
        data_json = client.get(key)

        if data_json is None:
            logger.debug(f"Cache miss: {key}")
            return None

        logger.info(f"Cache hit: {key}")
        return json.loads(data_json)

    except RedisError as e:
        logger.warning(f"Redis get error for key {key}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in cache for key {key}: {e}")
        # Delete corrupted cache entry
        try:
            client.delete(key)
        except:
            pass
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting cache key {key}: {e}")
        return None


def set_cached(key: str, data: dict, ttl: Optional[int] = None) -> bool:
    """
    Store data in cache with TTL.

    Args:
        key: Cache key to store under
        data: Dictionary to cache (must be JSON-serializable)
        ttl: Time-to-live in seconds (uses config default if None)

    Returns:
        True if successfully cached, False on error

    Note:
        Errors are logged but don't raise exceptions
    """
    settings = get_settings()

    # If caching is disabled, skip silently
    if not settings.CACHE_ENABLED:
        return False

    # Use configured TTL if not provided
    if ttl is None:
        ttl = settings.CACHE_TTL_SECONDS

    try:
        client = get_redis()
        data_json = json.dumps(data, ensure_ascii=False)

        client.setex(key, ttl, data_json)
        logger.info(f"Cache set: {key} (TTL: {ttl}s)")
        return True

    except (RedisError, json.JSONEncodeError) as e:
        logger.warning(f"Failed to cache key {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error setting cache key {key}: {e}")
        return False


def delete_cached(key: str) -> bool:
    """
    Delete a specific cache entry.

    Used for cache invalidation when data changes.

    Args:
        key: Cache key to delete

    Returns:
        True if key was deleted, False otherwise
    """
    try:
        client = get_redis()
        deleted = client.delete(key)

        if deleted:
            logger.info(f"Cache deleted: {key}")
            return True
        else:
            logger.debug(f"Cache key not found: {key}")
            return False

    except RedisError as e:
        logger.warning(f"Failed to delete cache key {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting cache key {key}: {e}")
        return False


def clear_cache(pattern: str = "*") -> int:
    """
    Bulk delete cache entries matching pattern.

    Used for admin operations or when clearing all cached data.

    Args:
        pattern: Redis key pattern (e.g., "chartspec:*")

    Returns:
        Count of deleted keys

    Warning:
        Use with caution in production - can be slow for large keyspaces
    """
    try:
        client = get_redis()
        settings = get_settings()

        # Build full pattern with prefix
        full_pattern = f"{settings.CACHE_KEY_PREFIX}:{pattern}"

        # Find matching keys
        keys = list(client.scan_iter(match=full_pattern, count=100))

        if not keys:
            logger.info(f"No keys found matching pattern: {full_pattern}")
            return 0

        # Delete in batches
        deleted = client.delete(*keys)
        logger.info(f"Cleared {deleted} cache keys matching pattern: {full_pattern}")
        return deleted

    except RedisError as e:
        logger.error(f"Failed to clear cache with pattern {pattern}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error clearing cache: {e}")
        return 0


def get_cache_stats() -> dict[str, Any]:
    """
    Get Redis cache statistics.

    Returns information about memory usage, hit rate, and keyspace.

    Returns:
        Dictionary with cache statistics, or empty dict on error
    """
    try:
        client = get_redis()
        info = client.info()

        return {
            "redis_version": info.get("redis_version"),
            "used_memory_human": info.get("used_memory_human"),
            "used_memory_peak_human": info.get("used_memory_peak_human"),
            "total_connections_received": info.get("total_connections_received"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "connected_clients": info.get("connected_clients"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {}
