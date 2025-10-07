import asyncio
import time
import pytest
from auto_workflow import task, flow
from auto_workflow.scheduler import execute_dag, FailurePolicy
from auto_workflow.build import BuildContext, collect_invocations

@task
async def slow(x: int):
    await asyncio.sleep(0.2)
    return x

@task
def aggregate(xs):
    return sum(xs)

@flow
def cancel_flow():
    items = [slow(1), slow(2), slow(3)]
    return aggregate(items)

@pytest.mark.asyncio
async def test_manual_cancellation():
    # Build manually to use low-level execute_dag with cancellation
    with BuildContext() as bctx:
        struct = cancel_flow.build_fn()
    invs = collect_invocations(struct)
    # Provide a cancellation event that fires after first task schedules
    cancel_event = asyncio.Event()
    async def trigger():
        await asyncio.sleep(0.05)
        cancel_event.set()
    asyncio.create_task(trigger())
    results = await execute_dag(invs, failure_policy=FailurePolicy.CONTINUE, max_concurrency=None, cancel_event=cancel_event)  # type: ignore
    # Some tasks likely cancelled; ensure partial results type OK
    finished = [v for v in results.values() if not isinstance(getattr(v, '__class__', object), type)]
    assert any(name.startswith('slow:') for name in results)

