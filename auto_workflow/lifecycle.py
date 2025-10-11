"""Lifecycle helpers for graceful shutdown of runtime components."""

from __future__ import annotations

from .execution import _shutdown_pool  # internal but intentional for lifecycle


def shutdown() -> None:
    """Gracefully shut down background resources (process pool, etc.).

    Safe to call multiple times.
    """
    try:
        _shutdown_pool()
    except Exception:
        pass
