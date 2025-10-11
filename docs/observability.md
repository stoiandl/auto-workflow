# Observability (Logging, Metrics, Tracing)

Observability is lightweight, pluggable, and enabled by default for structured logs.

## Events
Core events emitted (subscribe via `auto_workflow.subscribe`):
- `flow_started`
- `flow_completed`
- `task_started`
- `task_retry`
- `task_failed`
- `task_succeeded`

Example subscriber:
```python
from auto_workflow import subscribe

def on_flow_started(payload):
    print("flow started:", payload)

subscribe("flow_started", on_flow_started)
```

## Logging
Structured logging is registered by default at import-time and writes human-friendly pretty logs
to the `auto_workflow.tasks` logger. A stdout handler is attached by default.

You can control this via environment variables:
- `AUTO_WORKFLOW_DISABLE_STRUCTURED_LOGS=1` — disable structured logging entirely
- `AUTO_WORKFLOW_LOG_LEVEL=DEBUG|INFO|...` — change log level (default `INFO`)

Programmatic control:
```python
from auto_workflow.logging_middleware import register_structured_logging

register_structured_logging()     # idempotent; pretty output enabled by default
```

Emitted log events:
- `flow_started`: `flow`, `run_id`, `ts`
- `flow_completed`: `flow`, `run_id`, `tasks`, `ts`
- `task_started`: `task`, `node`, `ts`
- `task_ok`: `task`, `flow`, `run_id`, `ts`, `duration_ms`
- `task_err`: `task`, `flow`, `run_id`, `ts`, `duration_ms`, `error`

Example pretty output:
```
2025-10-12 00:22:48+0100 | INFO | flow_started | flow=etl_flow run_id=...
2025-10-12 00:22:48+0100 | INFO | task_started | task=extract_raw node=extract_raw:1
2025-10-12 00:22:48+0100 | INFO | task_ok | flow=etl_flow run_id=... task=extract_raw duration=56.2ms
2025-10-12 00:22:48+0100 | INFO | flow_completed | flow=etl_flow run_id=... tasks=4
```

## Metrics
The default in-memory provider records counters & simple histograms:
- `tasks_succeeded`
- `tasks_failed`
- `task_duration_ms`
- `cache_hits`
- `cache_sets`
- `dedup_joins` (number of followers waiting on an in-flight identical task)

Swap out the provider with your own implementation via `set_metrics_provider()`.

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
- Optional span sampling configuration

See the [Logging](#logging) section above for the built-in middleware and controls.
