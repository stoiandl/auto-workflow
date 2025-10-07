"""Middleware chaining for task execution (extensible)."""
from __future__ import annotations
from typing import Awaitable, Callable, Any, List

TaskCallable = Callable[[], Awaitable[Any]]
Middleware = Callable[[TaskCallable, Any, tuple, dict], Awaitable[Any]]

_registry: List[Middleware] = []

def register(mw: Middleware) -> None:
    _registry.append(mw)

def clear() -> None:  # pragma: no cover
    _registry.clear()

async def _call_chain(index: int, core: TaskCallable, task_def: Any, args: tuple, kwargs: dict) -> Any:
    if index == len(_registry):
        return await core()
    mw = _registry[index]
    async def nxt():
        return await _call_chain(index + 1, core, task_def, args, kwargs)
    return await mw(lambda: nxt(), task_def, args, kwargs)

def get_task_middleware_chain() -> Callable[[TaskCallable, Any, tuple, dict], Awaitable[Any]]:
    async def runner(core: TaskCallable, task_def: Any, args: tuple, kwargs: dict) -> Any:
        return await _call_chain(0, core, task_def, args, kwargs)
    return runner
