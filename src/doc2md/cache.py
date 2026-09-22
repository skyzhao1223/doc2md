"""Small in-memory LRU + TTL cache for conversion results.

Conversion of a document is deterministic for given bytes, so we key the
cache by SHA-256 of the document content. This makes pagination
(``offset`` continuation calls) cheap: the document is downloaded again but
not re-converted.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from threading import Lock

DEFAULT_TTL_SECONDS = 30 * 60
DEFAULT_MAX_ENTRIES = 32
DEFAULT_MAX_BYTES = 256 * 1024 * 1024  # total size of cached values


class ConversionCache:
    def __init__(
        self,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._size = 0
        self._lock = Lock()

    @staticmethod
    def content_key(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if time.monotonic() - stored_at > self._ttl:
                self._remove_locked(key)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._data:
                self._remove_locked(key)
            self._data[key] = (time.monotonic(), value)
            self._size += len(value)
            while self._data and (
                len(self._data) > self._max_entries or self._size > self._max_bytes
            ):
                oldest_key, _ = next(iter(self._data.items()))
                self._remove_locked(oldest_key)

    def _remove_locked(self, key: str) -> None:
        entry = self._data.pop(key, None)
        if entry is not None:
            self._size -= len(entry[1])


cache = ConversionCache()
