# Dynamic Fan-Out

Dynamic fan-out allows creating tasks only after an upstream result is known (runtime expansion). This supports scenarios where the number of follow-on tasks depends on data.

## Static vs Dynamic
Static fan-out (list comprehension) creates child task invocations during build:
```python
squares = [square(n) for n in numbers()]
```

Dynamic fan-out defers creation until upstream task result is available:
```python
from auto_workflow import task, flow, fan_out

@task
def list_urls() -> list[str]:
    return ["https://a", "https://b"]

@task
async def fetch(url: str) -> int:
    # return size
    ...

@task
def aggregate(sizes: list[int]) -> int:
    return sum(sizes)

@flow
def dynamic_flow():
    urls = list_urls()
    fetches = fan_out(fetch, iterable=urls)  # runtime expansion after list_urls completes
    return aggregate(fetches)

print(dynamic_flow.run())
```

## How It Works
- During build, `fan_out` detects the iterable is a `TaskInvocation` placeholder and creates a `DynamicFanOut` object.
- Scheduler waits for source task completion, obtains its (iterable) result, and creates child task invocations.
- Downstream tasks referencing the placeholder are rewired to depend on the new children.

## Constraints / Notes
- Source task must return an iterable (list/tuple/set). Non-iterables raise an error at runtime.
- Multi-level (nested) dynamic fan-out is partially supported but not yet hardened; avoid deep nesting for now.
- `max_concurrency` parameter is reserved; current implementation does not throttle dynamic expansion.

## When To Use
- Processing variable size batches.
- API fan-out where endpoints determined at runtime.
- Partitioned data ingestion (list partitions -> tasks per partition).
