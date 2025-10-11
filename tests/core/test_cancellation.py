import asyncio
import time

import pytest

from auto_workflow import flow, task
from auto_workflow.build import BuildContext, collect_invocations
from auto_workflow.scheduler import FailurePolicy, execute_dag


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
    with BuildContext():
        struct = cancel_flow.build_fn()
    invs = collect_invocations(struct)
    # Provide a cancellation event that fires after first task schedules
    cancel_event = asyncio.Event()

    async def trigger():
        await asyncio.sleep(0.05)
        cancel_event.set()

    asyncio.create_task(trigger())
    results = await execute_dag(
        invs, failure_policy=FailurePolicy.CONTINUE, max_concurrency=None, cancel_event=cancel_event
    )  # type: ignore
    # Some tasks likely cancelled; ensure partial results type OK
    # Removed unused finished variable; ensure partial results exist via name assertion
    assert any(name.startswith("slow:") for name in results)
