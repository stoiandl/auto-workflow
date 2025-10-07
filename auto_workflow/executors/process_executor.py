"""ProcessPool executor implementation (CPU-bound)."""
from __future__ import annotations
import asyncio
from concurrent.futures import ProcessPoolExecutor as _PPE
from typing import Any, Callable
import cloudpickle
from .base import BaseExecutor


_SHARED_POOL: _PPE | None = None

def get_process_pool() -> _PPE:
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = _PPE()
    return _SHARED_POOL


def run_pickled(payload: bytes) -> Any:  # executed in worker process
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)

class ProcessExecutor(BaseExecutor):  # retained for potential future explicit usage
    def __init__(self, max_workers: int | None = None) -> None:  # pragma: no cover
        self._pool = _PPE(max_workers=max_workers)
        self._loop = asyncio.get_event_loop()

    async def submit(self, node_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        return await self._loop.run_in_executor(self._pool, lambda: fn(*args, **kwargs))

    async def shutdown(self, cancel: bool = False) -> None:  # pragma: no cover
        self._pool.shutdown(wait=True, cancel_futures=cancel)
