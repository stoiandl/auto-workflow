"""ThreadPool executor implementation."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor as _TPE
from typing import Any, Callable
from .base import BaseExecutor


class ThreadExecutor(BaseExecutor):
    def __init__(self, max_workers: int | None = None) -> None:
        self._pool = _TPE(max_workers=max_workers)
        self._loop = asyncio.get_event_loop()

    async def submit(self, node_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self._loop.run_in_executor(self._pool, lambda: fn(*args, **kwargs))

    async def shutdown(self, cancel: bool = False) -> None:  # pragma: no cover - trivial
        self._pool.shutdown(wait=True, cancel_futures=cancel)
