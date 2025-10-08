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
A lightweight `DummyTracer` yields an async `span(name, **attrs)` context. Flows and each task execution are wrapped, providing hook points to inject OpenTelemetry or custom logging.

### What You Get
| Span Name Pattern | Attributes Provided | When Emitted |
|-------------------|--------------------|--------------|
| `flow:<flow_name>` | (future) `run_id` | At flow start/end |
| `task:<task_name>` | `node` (unique node id) | For every task execution |

### Custom Recording Tracer Example
See `examples/tracing_custom.py` for a richer script. Minimal inline version:
```python
from auto_workflow.tracing import set_tracer
from contextlib import asynccontextmanager
import time

class RecordingTracer:
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        start = time.time()
        try:
            yield
        finally:
            print(f"span={name} attrs={attrs} ms={(time.time()-start)*1000:.2f}")

set_tracer(RecordingTracer())
```

### OpenTelemetry Integration Sketch
```python
from contextlib import asynccontextmanager
from opentelemetry import trace
from auto_workflow.tracing import set_tracer

otel = trace.get_tracer("auto_workflow")

class OTELTracer:
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        with otel.start_as_current_span(name) as sp:
            for k,v in attrs.items():
                sp.set_attribute(k, v)
            try:
                yield
            except Exception as e:  # record & re-raise
                sp.record_exception(e)
                sp.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

set_tracer(OTELTracer())
```

### Planned Enhancements
- Error flag & retry metrics as span attributes
- Cache hit / dedup indicators
- Executor type annotation (`async|thread|process`)
- Optional span sampling configuration

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
