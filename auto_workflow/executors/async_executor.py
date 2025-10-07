"""AsyncIO executor implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .base import BaseExecutor


class AsyncExecutor(BaseExecutor):
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    async def submit(self, node_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        coro = fn(*args, **kwargs)
        if not asyncio.iscoroutine(coro):  # safety

            async def wrap(v: Any):
                return v

            coro = wrap(coro)  # type: ignore
        task = asyncio.create_task(coro)
        self._tasks[node_id] = task
        return await task

    async def shutdown(self, cancel: bool = False) -> None:
        if cancel:
            for t in self._tasks.values():
                t.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
