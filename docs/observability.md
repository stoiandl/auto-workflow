# Observability (Logging, Metrics, Tracing)

Observability surfaces are intentionally lightweight and pluggable.

## Events
Core events emitted (subscribe via `auto_workflow.subscribe`):
- `flow_started`
- `flow_completed`
- `task_started`
- `task_retry`
- `task_failed`
- `task_succeeded`

## Metrics
An in-memory metrics provider records counters & simple histograms:
- `tasks_succeeded`
- `tasks_failed`
- `task_duration_ms`

Extend by replacing provider (see extensibility section).

## Tracing
A `DummyTracer` implements an async context manager `span(name, **attrs)`. Replace with OpenTelemetry-compatible tracer:
```python
from auto_workflow.tracing import set_tracer, get_tracer

class OTelShim:
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, tb): ...
    async def span(self, name: str, **attrs):
        # return async context manager
        ...

set_tracer(OTelShim())
```
Spans currently wrap flows and each task execution.

## Logging
A dedicated logging middleware can serialize structured logs (add a custom middleware that emits JSON lines). Example skeleton:
```python
from auto_workflow.middleware import register
import json, time

async def log_mw(next_call, task_def, args, kwargs):
    start = time.time()
    try:
        result = await next_call()
        return result
    finally:
        print(json.dumps({
            "task": task_def.name,
            "ms": (time.time() - start) * 1000.0
        }))

register(log_mw)
```
