# Tasks

Tasks are the fundamental execution units. They are declared with the `@task` decorator which attaches metadata controlling retries, timeout, caching, persistence, execution mode, and priority.

## Basic Declaration
```python
from auto_workflow import task

@task
def add(a: int, b: int) -> int:
    return a + b
```

## Parameters
| Argument | Type | Description |
|----------|------|-------------|
| name | str | Override display / node name |
| retries | int | Number of retry attempts on failure (default 0) |
| retry_backoff | float | Base seconds for exponential backoff (2^(attempt-1)) |
| retry_jitter | float | Random jitter added to backoff duration |
| timeout | float | Max seconds before a task times out |
| cache_ttl | int | Cache lifetime in seconds (memory/filesystem backends) |
| cache_key_fn | Callable | Function producing cache key from (fn, args, kwargs) |
| run_in | str | One of: `"async"`, `"thread"`, `"process"` |
| persist | bool | If True, result stored via artifact store (returns `ArtifactRef`) |
| priority | int | Higher priority tasks schedule earlier when multiple ready |

## Execution Modes
- async (default): coroutine or regular function awaited in event loop
- thread: executed in thread pool (uses `asyncio.to_thread`)
- process: executed in process pool (cloudpickle for serialization)

## Retries & Backoff
```python
@task(retries=3, retry_backoff=1.5, retry_jitter=0.5)
async def fetch(url: str) -> str:
    ...
```
Backoff sequence (without jitter): 1.5s, 3.0s, 6.0s.

## Timeout Handling
If `timeout` elapses, a custom `TimeoutError` is raised and subject to retry until attempts exhausted.

## Caching
A cached task consults the configured result cache backend (default in-memory). If TTL not expired, execution is skipped and cached value is reused.

## Persistence
When `persist=True`, the raw result is stored and the task output becomes an `ArtifactRef`. Downstream tasks receive that reference and can resolve it:
```python
from auto_workflow.artifacts import get_store

@task(persist=True)
def large():
    return b"binary-payload" * 1024

@task
def size(ref):
    store = get_store()
    data = store.get(ref)
    return len(data)
```

## Priority
Priorities influence ordering ONLY among currently runnable tasks whose dependencies are satisfied. Higher numeric value wins.

## Immediate Execution
Calling a task outside a flow executes it immediately (respecting retries, timeout, persistence, tracing) and returns its value (or `ArtifactRef`).
