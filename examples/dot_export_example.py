import asyncio
import random
import time
from contextlib import asynccontextmanager

from auto_workflow import fan_out, flow, task
from auto_workflow.tracing import set_tracer


class RecordingTracer:
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        start = time.time()
        try:
            yield
        finally:
            print(f"span={name} attrs={attrs} ms={(time.time() - start) * 1000:.2f}")


set_tracer(RecordingTracer())


@task(run_in="process")
def load_numbers() -> list[int]:
    return [1, 2, 3, 4]


@task
async def square(x: int) -> int:
    await asyncio.sleep(random.randint(1, 3))  # Simulate an async operation
    return x * x


@task
def aggregate(values: list[int]) -> int:
    return sum(values)


@flow
def pipeline():
    nums = load_numbers()
    # Dynamic fan-out: create tasks for each number
    squared = fan_out(square, nums)
    squared_2 = fan_out(square, squared)  # Fan-out again on the squared results
    return aggregate(squared_2)


if __name__ == "__main__":
    dot = pipeline.export_dot()
    print(dot)
