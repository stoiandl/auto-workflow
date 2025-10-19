# ADLS2 Connector (Azure Data Lake Storage Gen2)

The ADLS2 connector provides a production-friendly, sync client over Azure Data Lake Storage Gen2 with lazy imports, robust error mapping, and ergonomic helpers.

## Installation

```bash
poetry install -E connectors-adls2
# or
poetry install -E connectors-all
```

## Quick usage

```python
from auto_workflow.connectors import adls2

with adls2.client("default") as fs:
    # Ensure container exists
    fs.create_container("bronze", exist_ok=True)
    fs.make_dirs("bronze", "events/2025-10-19", exist_ok=True)
    fs.upload_bytes(
        container="bronze",
        path="events/2025-10-19/sample.csv",
        data=b"id,name\n1,alice\n",
        content_type="text/csv",
        overwrite=True,
    )
    rows = list(fs.list_paths("bronze", prefix="events/2025-10-19/"))
```

## Authentication & connection

Pick one:

- Connection string (recommended):
  - Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__CONNECTION_STRING="..."`
  - Aliases: `__CONN_STR`, `__DSN`
- Account URL + DefaultAzureCredential (AAD-based):
  - Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__ACCOUNT_URL="https://<acct>.dfs.core.windows.net"`
  - Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__USE_DEFAULT_CREDENTIALS=true`
- Custom credential object (advanced): set via config/JSON overlay as `credential`.

### Environment overrides

Prefix: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__`

```bash
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__CONNECTION_STRING="DefaultEndpointsProtocol=..."
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__ACCOUNT_URL="https://myacct.dfs.core.windows.net"
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__USE_DEFAULT_CREDENTIALS=true
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__RETRIES__ATTEMPTS=5
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__TIMEOUTS__CONNECT_S=2.0
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__TIMEOUTS__OPERATION_S=30.0
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__JSON='{"connection_string":"..."}'
```

## Operations

- `upload_bytes(container, path, data, content_type=None, metadata=None, overwrite=True, chunk_size=None, timeout=None) -> etag`
- `download_bytes(container, path, start=None, end=None, timeout=None) -> bytes`
- `download_stream(container, path, chunk_size=None, timeout=None) -> Iterator[bytes]`
- `list_paths(container, prefix=None, recursive=True, timeout=None) -> Iterator[dict]`
- `exists(container, path, timeout=None) -> bool`
- `delete_path(container, path, recursive=False, timeout=None) -> None`
- `make_dirs(container, path, exist_ok=True, timeout=None) -> None`
- `create_container(container, exist_ok=True, timeout=None) -> None`

Notes:
- `content_type` uses Azure Blob `ContentSettings` under the hood when available.
- Errors map to project exceptions: `AuthError`, `NotFoundError`, `TimeoutError`, `TransientError`, `PermanentError` with status-aware mapping for `HttpResponseError`.
- Imports are lazy; missing extras yield an informative ImportError.

## Example flow

See `examples/adls_csv_flow.py` for a CSV roundtrip flow that creates a container, writes a CSV, reads it back, and cleans up.
