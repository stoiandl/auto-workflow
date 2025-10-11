"""Example: Mixed execution modes with multi-level dependencies.

Demonstrates:
- Multiple task levels (produce -> fan-out compute -> aggregate -> enrich -> finalize)
- A mix of run_in modes: process, thread (default for sync), async, and an immediate "normal" task
- Dynamic fan-out to parallelize CPU-heavy work
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any

from auto_workflow import fan_out, flow, task
from auto_workflow.artifacts import get_store


# --- Helpers for CPU-bound demo (runs best in a process) ---

def _fib(n: int) -> int:
    # intentionally naive to be CPU-heavy for small n
    if n <= 1:
        return n
    return _fib(n - 1) + _fib(n - 2)


# --- Tasks: Level 1 (seed) ---


@task
def seed_numbers(n: int = 4) -> list[int]:
    """Produce a small list of Fibonacci inputs (CPU-heavy but small)."""
    base = 22
    return [base + i for i in range(n)]  # e.g., 22, 23, 24, 25


# --- Tasks: Level 2 (parallel compute with different modes) ---


@task(run_in="process")
def fib_process(x: int) -> int:
    """CPU bound: executed in a process pool."""
    return _fib(x)


@task  # default for sync is thread to avoid blocking the event loop
def blocking_disk_stats() -> dict[str, Any]:
    """Pretend to read disk stats (blocking IO) -> runs in a thread by default."""
    time.sleep(0.05)
    return {"disk_free_gb": 128, "disk_used_gb": 64}


@task  # async task natively
async def fetch_remote_config() -> dict[str, Any]:
    await asyncio.sleep(0.05)
    return {"feature_flags": {"beta": True}, "threshold": 10}


# --- Tasks: Level 3 (aggregate) ---


@task
def aggregate_fibs(values: list[int]) -> dict[str, Any]:
    total = sum(values)
    return {"count": len(values), "sum": total, "avg": total / len(values)}


# --- Tasks: Level 4 (enrich + finalize) ---


@dataclass
class Report:
    meta: dict[str, Any]
    fib_stats: dict[str, Any]
    disk: dict[str, Any]


@task
def merge_report(fib_stats: dict[str, Any], cfg: dict[str, Any], disk: dict[str, Any]) -> Report:
    meta = {"config": cfg, "generated_at": time.time()}
    return Report(meta=meta, fib_stats=fib_stats, disk=disk)


@task(persist=True)
def persist_report(report: Report) -> Report:
    # Persist the dataclass as an artifact; the return value is stored and a ref is
    # substituted automatically when this task is used downstream.
    return report


# --- A standalone "normal" task call (immediate execution outside a flow) ---


@task
def square_local(x: int) -> int:
    # Runs immediately when called outside a flow (synchronous helper)
    return x * x


# --- Flow ---


@flow
def mixed_modes_flow(n: int = 4):
    # Level 1
    seeds = seed_numbers(n)

    # Level 2: dynamic fan-out (process pool for CPU-heavy work) + parallel async/thread tasks
    fib_values = fan_out(fib_process, seeds)
    disk = blocking_disk_stats()
    cfg = fetch_remote_config()

    # Level 3: aggregate CPU results
    fib_stats = aggregate_fibs(fib_values)

    # Level 4: merge and persist
    report = merge_report(fib_stats, cfg, disk)
    ref = persist_report(report)
    return ref


if __name__ == "__main__":
    # Demonstrate immediate task execution (outside a flow build)
    print("Immediate square_local(7) ->", square_local(7))

    # Run the mixed flow
    ref = mixed_modes_flow.run(max_concurrency=8)
    store = get_store()
    stored = store.get(ref)
    try:
        # If the artifact store returns the exact dataclass instance
        print("Stored report:", asdict(stored) if hasattr(stored, "__dict__") else stored)
    except Exception:  # noqa: BLE001 - robust printing regardless of serializer
        print("Stored report:", stored)
