# Extensibility

`auto-workflow` aims for a narrow waist: a minimal stable core with well-defined extension seams.

## Key Interfaces
| Area | Hook / API | Notes |
|------|------------|-------|
| Task execution | Middleware chain | Wrap or alter task run behavior |
| Scheduling | (internal) scheduler loop | Future: pluggable strategies (fairness, resources) |
| Caching | Result cache backend | Provide custom get/set persistence |
| Artifacts | Artifact store | Offload large results (e.g., S3) |
| Metrics | Metrics provider | Export counters/histograms externally |
| Tracing | Tracer | Bridge to OpenTelemetry or custom collectors |
| Secrets | Secrets provider | Integrate Vault, AWS SM, GCP Secret Manager |
| CLI | Subcommands | Add commands (e.g., deploy, ui) |

## Implementing a Custom Result Cache
```python
from auto_workflow.cache import ResultCache

class RedisResultCache:
    def __init__(self, client):
        self.client = client
    def get(self, key, ttl):
        data = self.client.get(key)
        if not data: return None
        ts, value = deserialize(data)
        if ttl is None: return None
        import time
        if time.time() - ts <= ttl:
            return value
        return None
    def set(self, key, value):
        self.client.set(key, serialize((time.time(), value)))
```
Wire it by monkeypatching `get_result_cache` or contributing a selection mechanism.

## OpenTelemetry Integration (Planned)
Implement a tracer with `async def span(name, **attrs)` context manager returning an object capturing attributes & exporting spans.

## UI / Visualization
Consumers can render DOT export via Graphviz or transform JSON adjacency list for a web UI (d3.js). A future optional UI module may subscribe to events in real time.
