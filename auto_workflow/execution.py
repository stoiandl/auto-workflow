"""Execution helpers for process-based task offload."""

from __future__ import annotations

import atexit
from concurrent.futures import ProcessPoolExecutor
from contextlib import suppress
from typing import Any

import cloudpickle

from .config import load_config

_SHARED_POOL: ProcessPoolExecutor | None = None


def _shutdown_pool() -> None:
    global _SHARED_POOL
    if _SHARED_POOL is not None:
        with suppress(Exception):
            _SHARED_POOL.shutdown(wait=True, cancel_futures=True)
        _SHARED_POOL = None


def get_process_pool() -> ProcessPoolExecutor:
    global _SHARED_POOL
    if _SHARED_POOL is None:
        cfg = load_config()
        max_workers = cfg.get("process_pool_max_workers")
        if isinstance(max_workers, str):
            try:
                max_workers = int(max_workers) if max_workers.isdigit() else None
            except Exception:
                max_workers = None
        if not isinstance(max_workers, int) or max_workers <= 0:
            max_workers = None
        _SHARED_POOL = ProcessPoolExecutor(max_workers=max_workers)
        # Ensure clean shutdown on interpreter exit
        atexit.register(_shutdown_pool)
    return _SHARED_POOL


def run_pickled(payload: bytes) -> Any:  # executed in worker process
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)
