from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    summary: dict[str, Any]
    expires_at: float
    insight: str | None = None


class AnalysisCache:
    """Small process-local TTL/LRU cache for trusted server summaries."""

    def __init__(self) -> None:
        self.max_items = max(1, int(os.getenv("ANALYSIS_CACHE_MAX_ITEMS", "100")))
        self.ttl_seconds = max(60, int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "1800")))
        self._items: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()

    def _remove_expired(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def put(self, analysis_id: str, summary: dict[str, Any]) -> None:
        with self._lock:
            now = time.monotonic()
            self._remove_expired(now)
            self._items[analysis_id] = CacheEntry(
                summary=summary,
                expires_at=now + self.ttl_seconds,
            )
            self._items.move_to_end(analysis_id)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)

    def get(self, analysis_id: str) -> CacheEntry | None:
        with self._lock:
            now = time.monotonic()
            self._remove_expired(now)
            item = self._items.get(analysis_id)
            if item is None:
                return None
            self._items.move_to_end(analysis_id)
            return CacheEntry(item.summary.copy(), item.expires_at, item.insight)

    def set_insight(self, analysis_id: str, insight: str) -> bool:
        with self._lock:
            now = time.monotonic()
            self._remove_expired(now)
            item = self._items.get(analysis_id)
            if item is None:
                return False
            item.insight = insight
            self._items.move_to_end(analysis_id)
            return True

