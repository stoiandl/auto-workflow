### ADLS2 CSV roundtrip

End-to-end example: `examples/adls_csv_flow.py`

This flow demonstrates:
- Ensuring a container exists
- Creating a folder
- Writing a small CSV
- Reading and printing its contents
- Cleaning up the created resources

Install (one-time):

```bash
# Install Azure extras (or install all connector extras)
poetry install -E connectors-adls2
# or
poetry install -E connectors-all
```

Environment (use the profile from the example: ADLS_TEST):

```bash
# Option A: connection string (recommended when available)
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__CONNECTION_STRING="DefaultEndpointsProtocol=..."

# Option B: account_url + DefaultAzureCredential (AAD-based)
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__ACCOUNT_URL="https://<acct>.dfs.core.windows.net"
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__USE_DEFAULT_CREDENTIALS=true

# Optional tuning
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__RETRIES__ATTEMPTS=5
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__TIMEOUTS__CONNECT_S=2.0
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__TIMEOUTS__OPERATION_S=30.0
```

Run:

```bash
# Prefer running inside Poetry's virtual environment
poetry run python examples/adls_csv_flow.py
```

Expected output:

```
CSV rows:
['id', 'name']
['1', 'alice']
['2', 'bob']
['3', 'cathy']
Flow returned 4 rows
```

Code (excerpt):

```python
from auto_workflow import flow, task
from auto_workflow.connectors import adls2
from datetime import UTC, datetime
import csv, io

@task
def ensure_container(container: str, profile: str) -> str:
    with adls2.client(profile=profile) as c:
        svc = c.datalake_service_client()
        create = getattr(svc, "create_file_system", None)
        if callable(create):
            create(file_system=container)
        else:
            _ = c.filesystem_client(container)
    return container

@task
def make_folder(container: str, folder: str, profile: str) -> str:
    with adls2.client(profile=profile) as c:
        c.make_dirs(container, folder, exist_ok=True)
    return folder

@task
def write_csv(container: str, folder: str, profile: str, filename: str = "sample.csv") -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name"])
    for r in [(1, "alice"), (2, "bob"), (3, "cathy")]:
        w.writerow(r)
    data = buf.getvalue().encode("utf-8")
    path = f"{folder.rstrip('/')}/{filename}"
    with adls2.client(profile=profile) as c:
        c.upload_bytes(container, path, data, content_type="text/csv", overwrite=True)
    return path

@task
def read_csv(container: str, path: str, profile: str) -> list[list[str]]:
    with adls2.client(profile=profile) as c:
        data = c.download_bytes(container, path)
    return list(csv.reader(io.StringIO(data.decode("utf-8"))))

@task
def cleanup(container: str, folder: str, path: str, profile: str) -> None:
    with adls2.client(profile=profile) as c:
        c.delete_path(container, path)
        c.delete_path(container, folder, recursive=True)

@flow
def adls_csv_flow(container: str = "demo-container", folder_prefix: str = "incoming", profile: str = "adls_test"):
    folder = f"{folder_prefix}/{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    ensured = ensure_container(container, profile)
    made = make_folder(ensured, folder, profile)
    path = write_csv(ensured, made, profile)
    rows = read_csv(ensured, path, profile)
    cleanup(ensured, made, path, profile)
    return rows
```

Troubleshooting:
- Ensure the Azure SDK extras are installed and you’re running inside the Poetry environment.
- Verify the environment variables are exported in your shell (printenv) and match the profile used by the example (`ADLS_TEST`).
- If your identity lacks permissions, switch to a connection string or adjust Azure RBAC/ACLs.
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
    transformed = fan_out(transform, extracted)  # dynamic mapping of previous dynamic results
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
    # For static known values, you can use list comprehension with static data
    results = [heavy(i) for i in range(5)]  # static: each heavy(0), heavy(1), etc.
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

## Example: Custom Tracing
```python
from auto_workflow.tracing import set_tracer
from contextlib import asynccontextmanager
import time

class RecordingTracer:
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        start = time.time()
        try:
            yield {"name": name, **attrs}
        finally:
            dur = (time.time() - start) * 1000.0
            print(f"span {name} attrs={attrs} dur_ms={dur:.2f}")

set_tracer(RecordingTracer())
```

## Example: Threaded Parallelism
```python
from auto_workflow import task, flow
import time

@task(run_in="thread")
def slow(i: int):
    time.sleep(0.05)
    return i

@flow
def parallel():
    return [slow(i) for i in range(4)]

print(parallel.run())
```
