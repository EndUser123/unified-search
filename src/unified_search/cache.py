"""Query Cache - LRU cache for repeated search queries."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any


class QueryCache:
    """LRU cache for search queries with TTL."""

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 300
    ):
        """Initialize query cache.

        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time-to-live for cache entries (default 5 min)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _hash_query(self, query: str, **kwargs) -> str:
        """Create hash from query string and options."""
        # Normalize query
        normalized = query.strip().lower()

        # Include options in hash
        options = sorted(kwargs.items())
        key_data = json.dumps({"q": normalized, "opts": options}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(
        self,
        query: str,
        **kwargs
    ) -> list[dict] | None:
        """
        Get cached results for query.

        Args:
            query: Search query string
            **kwargs: Additional query options

        Returns:
            Cached results or None if not found/expired
        """
        key = self._hash_query(query, **kwargs)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry["timestamp"] > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry["results"]

    def set(
        self,
        query: str,
        results: list[dict],
        **kwargs
    ) -> None:
        """
        Cache results for query.

        Args:
            query: Search query string
            results: Search results to cache
            **kwargs: Additional query options
        """
        key = self._hash_query(query, **kwargs)

        with self._lock:
            # Enforce size limit
            if len(self._cache) >= self.max_size:
                # Remove oldest (first) item
                self._cache.popitem(last=False)

            self._cache[key] = {
                "results": results,
                "timestamp": time.time(),
                "query": query,
                "kwargs": kwargs
            }

    def invalidate(self) -> None:
        """Invalidate all cache entries."""
        with self._lock:
            self._cache.clear()

    def clear(self) -> None:
        """Clear all cache entries (alias for invalidate)."""
        self.invalidate()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds
            }
