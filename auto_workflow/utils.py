"""Utility helpers."""
from __future__ import annotations
import inspect
import hashlib
import asyncio
from typing import Any, Callable

_DEF_HASH_SALT = b"auto_workflow:v1"

def default_cache_key(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        key_source = repr((fn.__module__, fn.__qualname__, sorted(bound.arguments.items())))
    except Exception:  # pragma: no cover - fallback
        key_source = repr((fn.__module__, fn.__qualname__, args, kwargs))
    digest = hashlib.sha256(_DEF_HASH_SALT + key_source.encode()).hexdigest()
    return digest

def is_coroutine_fn(fn: Callable[..., Any]) -> bool:
    while isinstance(fn, functools.partial):  # type: ignore
        fn = fn.func  # type: ignore
    return asyncio.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)

async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value

import functools  # placed after functions to avoid circular in is_coroutine_fn
