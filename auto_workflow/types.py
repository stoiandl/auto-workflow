"""Common type aliases and Protocols."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
R = TypeVar("R")

TaskFn = Callable[..., R] | Callable[..., Awaitable[R]]


@runtime_checkable
class SupportsHash(Protocol):
    def __hash__(self) -> int: ...  # pragma: no cover


CacheKey = str


class CancelledSentinel:
    def __repr__(self) -> str:  # pragma: no cover
        return "<CANCELLED>"


CANCELLED = CancelledSentinel()
