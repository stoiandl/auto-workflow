"""Example: Prioritized concurrent execution.

Demonstrates:
- priority scheduling (higher numbers first)
- mixing sync & async tasks
- tagging tasks
"""

from __future__ import annotations

import asyncio
import time

from auto_workflow import flow, task


@task(priority=1)
async def low_latency_call():
    await asyncio.sleep(0.05)
    return ("low", time.time())


@task(priority=10)
async def high_priority_call():
    await asyncio.sleep(0.02)
    return ("high", time.time())


@task(priority=5)
async def mid_priority_call():
    await asyncio.sleep(0.03)
    return ("mid", time.time())


@task
def order_summary(results):
    # results are (label, timestamp)
    ordered = sorted(results, key=lambda x: x[1])
    labels = [label for label, _ in ordered]
    return {"start_order": labels}


@flow
def priority_flow():
    a = low_latency_call()
    b = high_priority_call()
    c = mid_priority_call()
    # collect only after all three complete
    return order_summary([a, b, c])


if __name__ == "__main__":
    print(priority_flow.run())
