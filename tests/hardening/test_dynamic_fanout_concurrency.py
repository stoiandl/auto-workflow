import asyncio

from auto_workflow import flow, task
from auto_workflow.fanout import fan_out


def test_dynamic_fanout_respects_max_concurrency():
    peak = {"cur": 0, "max": 0}

    lock = asyncio.Lock()

    @task(run_in="async")
    async def probe(x: int) -> int:
        async with lock:
            peak["cur"] += 1
            peak["max"] = max(peak["max"], peak["cur"])
        await asyncio.sleep(0.02)
        async with lock:
            peak["cur"] -= 1
        return x

    @task(run_in="async")
    async def src() -> list[int]:
        return list(range(10))

    @flow
    def fl():
        items = src()
        # request a strict concurrency limit of 3 for the expansion
        results = fan_out(probe, items, max_concurrency=3)
        return results

    out = fl.run()
    assert sorted(out) == list(range(10))
    # peak observed should not exceed requested limit (allow a small margin for scheduling jitter)
    assert peak["max"] <= 3
