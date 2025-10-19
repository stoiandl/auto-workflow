"""Result cache abstraction with pluggable backends."""

from __future__ import annotations

import hashlib
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Protocol

from .config import load_config


class ResultCache(Protocol):  # pragma: no cover - interface
    def get(self, key: str, ttl: int | None) -> Any | None: ...
    def set(self, key: str, value: Any) -> None: ...


class InMemoryResultCache:
    def __init__(self) -> None:
        # Use OrderedDict for LRU semantics when bounding entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str, ttl: int | None) -> Any | None:
        if ttl is None:
            return None
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts <= ttl:
            # mark as recently used for LRU
            from contextlib import suppress

            with suppress(Exception):
                self._store.move_to_end(key)
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)
        # mark as recently used
        from contextlib import suppress

        with suppress(Exception):
            self._store.move_to_end(key)
        # enforce optional LRU bound
        cfg = load_config()
        max_entries_val = cfg.get("result_cache_max_entries")

        def _to_int(val):
            try:
                if val is None:
                    return None
                return int(str(val).strip())
            except Exception:
                return None

        max_entries = _to_int(max_entries_val)
        if max_entries is None:
            # Fallback to environment directly if config normalization preserved a string
            import os

            max_entries = _to_int(os.getenv("AUTO_WORKFLOW_RESULT_CACHE_MAX_ENTRIES"))

        if max_entries is not None and max_entries > 0:
            while len(self._store) > max_entries:
                try:
                    self._store.popitem(last=False)
                except Exception:
                    break


class FileSystemResultCache(InMemoryResultCache):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # use sha256 to create a filesystem-safe path; shard into 2-level dirs
        h = hashlib.sha256(key.encode()).hexdigest()
        shard1, shard2 = h[:2], h[2:4]
        p = self.root / shard1 / shard2
        p.mkdir(parents=True, exist_ok=True)
        return p / h

    def get(self, key: str, ttl: int | None) -> Any | None:  # type: ignore[override]
        p = self._path(key)
        if p.exists():
            try:
                with p.open("rb") as f:
                    ts, value = pickle.load(f)
                if ttl is not None and time.time() - ts <= ttl:
                    return value
            except Exception:  # pragma: no cover
                pass
        return super().get(key, ttl)

    def set(self, key: str, value: Any) -> None:  # type: ignore[override]
        super().set(key, value)
        p = self._path(key)
        try:
            with p.open("wb") as f:
                pickle.dump((time.time(), value), f)
        except Exception:  # pragma: no cover
            pass


_memory_cache = InMemoryResultCache()


def get_result_cache() -> ResultCache:
    cfg = load_config()
    backend = cfg.get("result_cache", "memory")
    if backend == "filesystem":
        from pathlib import Path

        root = Path(cfg.get("result_cache_path", ".aw_cache"))
        return FileSystemResultCache(root)
    return _memory_cache
