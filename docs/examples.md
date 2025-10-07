# Examples

## Example: ETL Mini-Pipeline
```python
from auto_workflow import task, flow, fan_out

@task
def extract_sources() -> list[str]:
    return ["source_a", "source_b"]

@task
def extract(name: str) -> dict:
    return {"name": name, "rows": [1,2,3]}

@task
def transform(batch: dict) -> dict:
    return {**batch, "rows": [r*2 for r in batch["rows"]]}

@task(persist=True)
def load(batches: list[dict]) -> int:
    # pretend to write to warehouse
    return sum(len(b["rows"]) for b in batches)

@flow
def etl():
    srcs = extract_sources()
    extracted = fan_out(extract, srcs)   # dynamic mapping
    transformed = [transform(b) for b in extracted]  # static mapping of previous dynamic children
    return load(transformed)

print(etl.run())
```

## Example: Caching & Priority
```python
@task(cache_ttl=300, priority=10)
def config(): return {"threshold": 5}

@task(priority=1)
def heavy(x: int): return compute(x)

@flow
def prioritized():
    cfg = config()
    results = [heavy(i) for i in range(5)]
    return results, cfg
```

## Example: Secrets
```python
from auto_workflow.secrets import secret, StaticMappingSecrets, set_secrets_provider
set_secrets_provider(StaticMappingSecrets({"TOKEN": "abc"}))

@task
def use_secret():
    return secret("TOKEN")
```

## Example: Timeout + Retry
```python
@task(retries=2, retry_backoff=1.0, timeout=3)
async def external_call():
    ...
```

## Example: ArtifactRef Handling
```python
from auto_workflow.artifacts import get_store

@task(persist=True)
def produce_big():
    return list(range(100000))

@task
def consume(ref):
    data = get_store().get(ref)
    return len(data)
```
