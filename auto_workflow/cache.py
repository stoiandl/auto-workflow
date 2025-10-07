"""Result cache abstraction with pluggable backends."""
from __future__ import annotations
from typing import Any, Protocol, Optional
import time, pickle
from pathlib import Path
from .config import load_config

class ResultCache(Protocol):  # pragma: no cover - interface
    def get(self, key: str, ttl: Optional[int]) -> Any | None: ...
    def set(self, key: str, value: Any) -> None: ...

class InMemoryResultCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
    def get(self, key: str, ttl: Optional[int]) -> Any | None:
        if ttl is None:
            return None
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts <= ttl:
            return value
        return None
    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

class FileSystemResultCache(InMemoryResultCache):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
    def _path(self, key: str) -> Path:
        return self.root / key
    def get(self, key: str, ttl: Optional[int]) -> Any | None:  # type: ignore[override]
        p = self._path(key)
        if p.exists():
            try:
                with p.open('rb') as f:
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
            with p.open('wb') as f:
                pickle.dump((time.time(), value), f)
        except Exception:  # pragma: no cover
            pass

_memory_cache = InMemoryResultCache()

def get_result_cache() -> ResultCache:
    cfg = load_config()
    backend = cfg.get('result_cache', 'memory')
    if backend == 'filesystem':
        from pathlib import Path
        root = Path(cfg.get('result_cache_path', '.aw_cache'))
        return FileSystemResultCache(root)
    return _memory_cache
