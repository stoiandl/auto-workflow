"""Example: Retry & timeout behavior.

Demonstrates:
- retries with backoff
- timeout handling
- distinguishing success after transient failures
"""

from __future__ import annotations

import asyncio
import random

from auto_workflow import flow, task

_attempts = {"n": 0}


@task(retries=3, retry_backoff=0.05)
async def flaky_call():
    _attempts["n"] += 1
    # Random transient failure
    if _attempts["n"] < 3:
        await asyncio.sleep(0.02)
        raise RuntimeError("temporary outage")
    await asyncio.sleep(0.01)
    return "ok after retries"


@task(timeout=0.05)
async def slow_maybe():
    # 50% chance to exceed timeout
    d = 0.1 if random.random() < 0.5 else 0.01
    await asyncio.sleep(d)
    return f"slept {d:.2f}s"


@flow
def reliability_demo():
    a = flaky_call()
    b = slow_maybe()
    return {"flaky": a, "maybe": b, "attempts": _attempts["n"]}


if __name__ == "__main__":
    try:
        print(reliability_demo.run())
    except Exception as e:  # noqa: BLE001
        print("Flow encountered an error:", e)
