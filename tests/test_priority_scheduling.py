import asyncio
import time

from auto_workflow import flow, task

start_times = {}
launch_order = []


@task(priority=1)
async def low():
    start_times["low"] = time.monotonic()
    launch_order.append("low")
    await asyncio.sleep(0.01)
    return "low"


@task(priority=10)
async def high():
    start_times["high"] = time.monotonic()
    launch_order.append("high")
    await asyncio.sleep(0.01)
    return "high"


@task(priority=5)
async def mid():
    start_times["mid"] = time.monotonic()
    launch_order.append("mid")
    await asyncio.sleep(0.01)
    return "mid"


@task
def collect(a, b, c):
    return [a, b, c]


@flow
def priority_flow():
    a = low()
    b = high()
    c = mid()
    return collect(a, b, c)


def test_priority_order():
    start_times.clear()
    priority_flow.run()
    # Validate ordering: high > mid > low (earlier schedule => smaller timestamp)
    # High must appear before low in launch order
    assert "high" in launch_order and "low" in launch_order
    assert launch_order.index("high") < launch_order.index("low")
