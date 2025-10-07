"""Middleware chaining for task execution (extensible)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .events import emit

TaskCallable = Callable[[], Awaitable[Any]]
Middleware = Callable[[TaskCallable, Any, tuple, dict], Awaitable[Any]]

_registry: list[Middleware] = []


def register(mw: Middleware) -> None:
    _registry.append(mw)


def clear() -> None:  # pragma: no cover
    _registry.clear()


async def _call_chain(
    index: int, core: TaskCallable, task_def: Any, args: tuple, kwargs: dict
) -> Any:
    if index == len(_registry):
        return await core()
    mw = _registry[index]
    executing_core = False

    async def nxt():
        nonlocal executing_core
        executing_core = True
        return await _call_chain(index + 1, core, task_def, args, kwargs)

    try:
        return await mw(lambda: nxt(), task_def, args, kwargs)
    except Exception as e:  # noqa: BLE001
        # If exception occurred during/after core execution, propagate (task error)
        if executing_core:
            raise
        # Otherwise classify as middleware error and continue chain
        emit(
            "middleware_error",
            {
                "task": getattr(task_def, "name", "unknown"),
                "middleware_index": index,
                "error": repr(e),
            },
        )
        return await _call_chain(index + 1, core, task_def, args, kwargs)


def get_task_middleware_chain() -> Callable[[TaskCallable, Any, tuple, dict], Awaitable[Any]]:
    async def runner(core: TaskCallable, task_def: Any, args: tuple, kwargs: dict) -> Any:
        return await _call_chain(0, core, task_def, args, kwargs)

    return runner
