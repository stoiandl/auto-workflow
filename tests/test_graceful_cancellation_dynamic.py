import asyncio
import pytest
from auto_workflow import task, flow, fan_out
from auto_workflow.build import BuildContext, collect_invocations
from auto_workflow.scheduler import execute_dag, FailurePolicy

@task
async def source():
    await asyncio.sleep(0.01)
    return [1,2,3,4]

@task
async def slow(x):
    await asyncio.sleep(0.05)
    return x

@flow
def dyn_flow():
    items = source()
    mapped = fan_out(slow, items)
    return mapped

@pytest.mark.asyncio
async def test_graceful_cancellation_dynamic():
    with BuildContext():
        struct = dyn_flow.build_fn()
    invs = collect_invocations(struct)
    cancel = asyncio.Event()
    async def trigger():
        await asyncio.sleep(0.03)
        cancel.set()
    trig_task = asyncio.create_task(trigger())
    results = await execute_dag(invs, failure_policy=FailurePolicy.CONTINUE, cancel_event=cancel)  # type: ignore
    await trig_task
    # Some tasks may be missing; ensure at least source executed.
    assert any(name.startswith('source:') for name in results)
