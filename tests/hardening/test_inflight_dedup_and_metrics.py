import asyncio

from auto_workflow import flow, task
from auto_workflow.metrics_provider import InMemoryMetrics, get_metrics_provider, set_metrics_provider


def test_inflight_dedup_metrics_and_exec_count():
    # fresh metrics provider for clean counters
    set_metrics_provider(InMemoryMetrics())

    exec_count = {"n": 0}

    @task(cache_ttl=10, run_in="async")
    async def slow(x: int) -> int:
        exec_count["n"] += 1
        await asyncio.sleep(0.05)
        return x * 2

    @flow
    def f():
        # invoke the same task multiple times with identical args to trigger de-dup
        return [slow(1) for _ in range(10)]

    out = f.run()
    assert all(v == 2 for v in out)
    # Only one actual execution should have happened due to inflight de-dup
    assert exec_count["n"] == 1
    mp = get_metrics_provider()
    # 1 cache_set for the first completion, 9 dedup joins for followers; cache_hits may be zero here
    assert mp.counters.get("cache_sets", 0) >= 1
    assert mp.counters.get("dedup_joins", 0) >= 9

