# Caching & Artifacts

Two related mechanisms help control recomputation and large payload handling: result caching and artifact persistence.

## Result Cache
Enable per task with `cache_ttl` (seconds):
```python
@task(cache_ttl=600)
def expensive(x: int) -> int:
    return compute(x)
```
If a cached entry is present and fresh, the task body is skipped.

### Backends
Configured via `load_config()` values:
- `result_cache = "memory"` (default)
- `result_cache = "filesystem"` -> stores pickled `(timestamp, value)` in path specified by `result_cache_path` (default `.aw_cache`).

## Cache Key
Default key uses function qualname + argument serialization (via a deterministic string builder). Override with `cache_key_fn`.

## Artifact Persistence
For large results, mark task as `persist=True`:
```python
@task(persist=True)
def produce():
    return {"data": list(range(1000))}
```
The output becomes an `ArtifactRef` (lightweight handle). Retrieve the underlying value:
```python
from auto_workflow.artifacts import get_store
val = get_store().get(ref)
```

### Artifact Backends
- Memory (default)
- Filesystem (`artifact_store = "filesystem"`, directory `artifact_store_path`, default `.aw_artifacts`)
    - Serializer: `artifact_serializer = "pickle"` (default) or `"json"` (JSON-serializable values only).
    - Security note: Pickle is only safe in trusted environments; prefer `json` for simple types.
    - Implementation writes/reads directly to disk to avoid keeping duplicate in-memory copies in the FS backend.

## Choosing Between Cache & Artifact
| Use Case | Mechanism |
|----------|-----------|
| Avoid re-running deterministic expensive function | Result Cache |
| Pass large payload downstream without duplicating in memory | Artifact (persist=True) |
| Both (skip recompute + offload memory) | persist + cache_ttl |
