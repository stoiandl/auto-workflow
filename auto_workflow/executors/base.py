"""Base executor protocol and common utilities."""
from __future__ import annotations
from typing import Any, Callable, Protocol, List

class BaseExecutor(Protocol):
    async def submit(self, node_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any: ...  # pragma: no cover
    async def shutdown(self, cancel: bool = False) -> None: ...  # pragma: no cover
