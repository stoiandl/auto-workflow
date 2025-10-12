import asyncio

from auto_workflow import flow, task
from auto_workflow.fanout import fan_out


@task
def make_batches(n: int) -> list[int]:
    return list(range(n))


@task
async def work(x: int) -> int:
    await asyncio.sleep(0)
    return x + 1


@task
def combine(vals: list[int]) -> int:
    return sum(vals)


@flow
def nested_dynamic(n: int = 4):
    batches = make_batches(n)
    first = fan_out(work, batches, max_concurrency=2)
    # Nested dynamic fan-out: apply the same work again to the dynamic output
    second = fan_out(work, first, max_concurrency=3)
    return combine(second)


def test_nested_dynamic_fanout():
    out = nested_dynamic.run()
    # make_batches(4) -> [0,1,2,3]; first work -> [1,2,3,4]; second work -> [2,3,4,5]
    assert out == sum([2, 3, 4, 5])
