"""ProcessPool executor implementation (CPU-bound)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import cloudpickle

from .base import BaseExecutor

_SHARED_POOL: ProcessPoolExecutor | None = None


def get_process_pool() -> ProcessPoolExecutor:
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = ProcessPoolExecutor()
    return _SHARED_POOL


def run_pickled(payload: bytes) -> Any:  # executed in worker process
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)


class ProcessExecutor(BaseExecutor):  # retained for potential future explicit usage
    def __init__(self, max_workers: int | None = None) -> None:  # pragma: no cover
        self._pool = ProcessPoolExecutor(max_workers=max_workers)
        self._loop = asyncio.get_event_loop()

    async def submit(
        self, node_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:  # pragma: no cover
        return await self._loop.run_in_executor(self._pool, lambda: fn(*args, **kwargs))

    async def shutdown(self, cancel: bool = False) -> None:  # pragma: no cover
        self._pool.shutdown(wait=True, cancel_futures=cancel)
