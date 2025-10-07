from auto_workflow import flow, task
from auto_workflow.metrics_provider import (
    InMemoryMetrics,
    get_metrics_provider,
    set_metrics_provider,
)
from auto_workflow.middleware import clear, register

_events = []


async def timing_mw(nxt, task_def, args, kwargs):
    _events.append(("before", task_def.name))
    res = await nxt()
    _events.append(("after", task_def.name))
    return res


@task
def compute():
    return 41


@task
def plus_one(x: int):
    return x + 1


@flow
def pipe():
    x = compute()
    y = plus_one(x)
    return y


def test_middleware_and_metrics():
    clear()
    register(timing_mw)
    # fresh metrics provider
    mp = InMemoryMetrics()
    set_metrics_provider(mp)
    out = pipe.run()
    assert out == 42
    assert ("before", "compute") in _events or ("before", "plus_one") in _events
    assert mp.counters.get("tasks_succeeded", 0) >= 2
