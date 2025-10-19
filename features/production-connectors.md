# Feature: Production‑grade Connectors (Postgres, S3, ADLS2)

Status: In progress (Postgres: implemented and tested; ADLS2: implemented behind extras; S3: pending)
Owner: TBD
Target version: LATEST_UNRELEASED_VERSION

## Why
Users need reliable, observable, and safe integrations with external systems from within tasks. This feature introduces a first‑class connectors/ package providing production‑ready clients for common backends (Postgres, AWS S3, Azure ADLS2) with consistent APIs, typed interfaces, robust error handling, timeouts/retries aligned with auto_workflow policies, and strong observability (events/metrics/tracing).

This design follows the stricter Builder Agent policy (production system): small, safe, reversible changes; clear boundaries; no hidden global state; optional runtime deps via extras; hermetic unit tests; and docs.

## Goals
- Stable, typed, minimal API surface for common operations per backend.
- Safe by default: timeouts, cancellation, retry classification, resource cleanup.
- Observable: tracing spans, metrics, structured events consistent with existing middleware.
- Backward compatible: new package only; no breaking changes to existing public APIs.
- Dependency isolation: heavy SDKs behind optional extras; lazy import with clear guidance.
- Config + secrets: first‑class integration with `auto_workflow.config` and `auto_workflow.secrets`.
- Testable: mockable interfaces, contract tests; no network calls in unit tests.

## Non‑Goals
- Full ORM or query builders (Postgres): we provide a thin, safe client with pooling.
- Full S3/ADLS2 surface: focus on high‑value ops (get/put/list/delete, streaming, multipart).
- Custom job schedulers or file watchers.

## Package layout
```
auto_workflow/
  connectors/
    __init__.py           # exports registry + base types + common exceptions
    base.py               # Base interfaces & lifecycle contracts
    registry.py           # Connector discovery/registry, lazy loading, profile keys
    exceptions.py         # ConnectorError hierarchy (Transient, Permanent, Auth, Timeout)
    types.py              # Typed configs & protocol definitions
    utils.py              # Shared helpers (timeouts, streaming, redaction)
    postgres.py           # Psycopg3 pool-backed client (sync, optional async)
    s3.py                 # boto3 client wrapper (+ optional aioboto3)
    adls2.py              # azure-storage-blob/dfs wrapper

tests/
  connectors/
    test_contracts.py
    test_registry.py
    test_postgres_unit.py
    test_s3_unit.py
    test_adls2_unit.py
  # Optional integration (skipped by default):
  connectors_integration/
    test_postgres_integration.py
    test_s3_integration.py
    test_adls2_integration.py
```

## Public API (high‑level)
- `auto_workflow.connectors.get(name: Literal["postgres","s3","adls2"], profile: str = "default") -> BaseConnector`
- `auto_workflow.connectors.postgres.client(profile: str = "default") -> PostgresClient`
- `auto_workflow.connectors.s3.client(profile: str = "default") -> S3Client`
- `auto_workflow.connectors.adls2.client(profile: str = "default") -> ADLS2Client`

Native access (escape hatches; see details below):
- Postgres: `connection()` (context manager yielding `psycopg.Connection`), `raw_pool()` (`psycopg_pool.ConnectionPool`), optional `sqlalchemy_engine()` if SQLAlchemy is installed.
- S3: `boto3_client()` (`botocore.client.S3`), `boto3_resource()` (`boto3.resources.factory.s3.ServiceResource`).
- ADLS2: `datalake_service_client()` (`azure.storage.filedatalake.DataLakeServiceClient`), `filesystem_client(container)`.

Notes:
- Clients are context managers; they ensure proper close/return to pool.
- Provide both sync methods; async variants may be provided where the upstream SDK supports it and where auto_workflow’s async execution model benefits. We’ll gate async behind `client.async()` factories or `Async*Client` classes, without breaking sync users.
- All clients accept per‑call overrides: timeout, retry policy, headers/metadata.

### API sketch (illustrative)
```python
from auto_workflow.connectors import postgres, s3, adls2

# Postgres
with postgres.client("analytics") as db:
    rows = db.query("SELECT id, name FROM users WHERE id = %s", (user_id,))
    db.execute("INSERT INTO events(...) VALUES (...)")

# S3
with s3.client("default") as s3c:
    s3c.put_object(bucket="raw", key="path/file.json", body=b"{}", content_type="application/json")
    stream = s3c.get_object(bucket="raw", key="path/file.json")  # returns an iterator/stream
    for chunk in stream:
        process(chunk)

# ADLS2
with adls2.client("lake") as fs:
    fs.upload_bytes(container="bronze", path="events/2025-10-18/file.json", data=b"{}")
    for path in fs.list_paths(container="bronze", prefix="events/2025-10-18/"):
        ...
```

## Connector APIs (contracts)
Concrete method signatures, inputs/outputs, and error modes. All methods can raise `ConnectorError` subclasses; we document key cases. All I/O supports `timeout: float | None` as seconds and accepts `retry: RetryConfig | None` (optional override of profile).

### Postgres
Types: `Row = dict[str, Any]` (dict-based rows), can be extended to typed rows later.

Class: `PostgresClient`
- Lifecycle:
  - `__enter__/__exit__`, `close()`, `is_closed() -> bool`
- Query execution:
  - `query(sql: str, params: tuple | dict | None = None, *, fetch: Literal["all","one","many"] = "all", size: int | None = None, timeout: float | None = None) -> list[Row] | Row | list[Row]`
    - Errors: `TimeoutError`, `TransientError` (e.g., serialization failure, deadlock), `PermanentError` (syntax), `AuthError` (auth), `ConfigError`
  - `execute(sql: str, params: tuple | dict | None = None, *, timeout: float | None = None) -> int` (rowcount)
  - `executemany(sql: str, seq_of_params: list[tuple | dict], *, timeout: float | None = None) -> int` (total rowcount)
- Transactions:
  - `transaction(isolation: Literal["read_committed","repeatable_read","serializable"] = "read_committed", *, readonly: bool = False, deferrable: bool = False, timeout: float | None = None) -> ContextManager[PostgresClient]`
    - Returns a context manager where queries are part of the transaction; commit on exit if no error, else rollback.
- Bulk operations:
  - `copy_from(table: str, file_or_iter: IO[bytes] | Iterable[bytes], *, columns: list[str] | None = None, format: Literal["csv","binary"] = "csv", delimiter: str = ",", timeout: float | None = None) -> int` (rows ingested)
  - `copy_to(table: str, file_like: IO[bytes], *, columns: list[str] | None = None, format: Literal["csv","binary"] = "csv", delimiter: str = ",", timeout: float | None = None) -> int` (rows exported)
 - Native access:
   - `connection() -> ContextManager[psycopg.Connection]` (checked‑out connection from pool; returns to pool on exit)
   - `raw_pool() -> psycopg_pool.ConnectionPool` (do not close externally; lifecycle managed by connector)
   - `sqlalchemy_engine() -> sqlalchemy.Engine` (optional, only if SQLAlchemy installed; behind optional extra)

### S3
Types:
- `ObjectInfo = dict[str, Any]` with keys like `bucket`, `key`, `size`, `last_modified`, `etag`.
- Streaming response wrapper: `class S3Body(Iterator[bytes]): close()` (context‑managed).

Class: `S3Client`
- Lifecycle: context manager, `close()` (idempotent)
- Put/Upload:
  - `put_object(bucket: str, key: str, body: bytes | IO[bytes], *, content_type: str | None = None, metadata: dict[str, str] | None = None, sse: str | None = None, acl: str | None = None, timeout: float | None = None) -> str` (ETag)
  - `upload_file(path: str, bucket: str, key: str, *, content_type: str | None = None, metadata: dict[str, str] | None = None, sse: str | None = None, timeout: float | None = None) -> str` (ETag)
- Get/Download:
  - `get_object(bucket: str, key: str, *, range: str | None = None, timeout: float | None = None) -> S3Body` (context‑managed iterator over bytes; has `close()`)
  - `download_file(bucket: str, key: str, path: str, *, timeout: float | None = None) -> None`
- Listing & delete:
  - `list_objects(bucket: str, prefix: str | None = None, *, recursive: bool = True, max_keys: int | None = None, timeout: float | None = None) -> Iterator[ObjectInfo]`
  - `delete_object(bucket: str, key: str, *, timeout: float | None = None) -> None`
  - `delete_prefix(bucket: str, prefix: str, *, timeout: float | None = None) -> int` (objects deleted)
- Errors: `NotFoundError` for missing objects, `AuthError`, `TimeoutError`, `TransientError` (throttling, 5xx), `PermanentError`.
 - Native access:
   - `boto3_client() -> botocore.client.S3`
   - `boto3_resource() -> boto3.resources.factory.s3.ServiceResource`

### ADLS2
Types: `PathInfo = dict[str, Any]` with `container`, `path`, `is_directory`, `size`, `last_modified`, `etag`.

Class: `ADLS2Client`
- Lifecycle: context manager, `close()`
- Upload/Download:
  - `upload_bytes(container: str, path: str, data: bytes | IO[bytes], *, content_type: str | None = None, metadata: dict[str, str] | None = None, overwrite: bool = True, chunk_size: int | None = None, timeout: float | None = None) -> str` (etag)
  - `download_bytes(container: str, path: str, *, start: int | None = None, end: int | None = None, timeout: float | None = None) -> bytes`
  - `download_stream(container: str, path: str, *, chunk_size: int | None = None, timeout: float | None = None) -> Iterator[bytes]`
- Listing & existence:
  - `list_paths(container: str, prefix: str | None = None, *, recursive: bool = True, timeout: float | None = None) -> Iterator[PathInfo]`
  - `exists(container: str, path: str, *, timeout: float | None = None) -> bool`
- Delete & directories:
  - `delete_path(container: str, path: str, *, recursive: bool = False, timeout: float | None = None) -> None`
  - `make_dirs(container: str, path: str, *, exist_ok: bool = True, timeout: float | None = None) -> None`
   - Containers:
     - `create_container(container: str, *, exist_ok: bool = True, timeout: float | None = None) -> None`
- Errors: `NotFoundError`, `AuthError`, `TimeoutError`, `TransientError` (server busy), `PermanentError`.
 - Native access:
   - `datalake_service_client() -> azure.storage.filedatalake.DataLakeServiceClient`
   - `filesystem_client(container: str) -> azure.storage.filedatalake.FileSystemClient`

## Contracts & Types
- Base interfaces (`base.py`):
  - `Connector`: lifecycle hooks (`open()`, `close()`, context manager), idempotent close, `is_closed()`
  - `SupportsTracing`, `SupportsMetrics`, `SupportsEvents` mixins
  - `Retryable`: `classify_error(exc) -> Transient|Permanent|Auth|Timeout`
  - `TimeoutConfig`, `RetryConfig` (backoff, jitter, max attempts, total timeout)
- Errors (`exceptions.py`):
  - `ConnectorError` -> `TransientError`, `PermanentError`, `AuthError`, `TimeoutError`, `ConfigError`, `NotFoundError`
- Types (`types.py`):
  - `PostgresConfig` (dsn | host/port/db/user, sslmode, pool params, statement_timeout)
  - `S3Config` (region, endpoint_url, sts_role, sse, retries, addressing_style)
  - `ADLS2Config` (account_url, credential kind: sas | key | workload_identity | client_secret)

## Configuration & Secrets
- Bind to existing config/secrets mechanisms:
  - Read profiles under `connectors.<name>.<profile>` from `auto_workflow.config`.
  - Resolve sensitive fields via `auto_workflow.secrets` by reference (e.g., `secret://env/POSTGRES_PASSWORD`).
- Example (YAML/TOML‑like, illustrative):
```
connectors:
  postgres:
    analytics:
      dsn: "postgresql://user:secret://env/PG_PASSWORD@host:5432/db?sslmode=require"
      pool:
        min_size: 1
        max_size: 10
        max_idle: 300s
      timeouts:
        connect: 5s
        statement: 30s
      retries:
        attempts: 3
        backoff: 100ms..2s (jitter)
  s3:
    default:
      region: "us-east-1"
      endpoint_url: null
      credentials:
        access_key_id: "secret://env/AWS_ACCESS_KEY_ID"
        secret_access_key: "secret://env/AWS_SECRET_ACCESS_KEY"
        session_token: "secret://env/AWS_SESSION_TOKEN"  # optional
      sse: "AES256"  # or KMS key id
      retries:
        attempts: 5
        mode: "adaptive"
  adls2:
    lake:
      account_url: "https://<account>.dfs.core.windows.net"
      use_default_credentials: true
      # or: connection_string = "DefaultEndpointsProtocol=..."
      retries:
        attempts: 5
```
- Profiles are named scopes. Callers can override with explicit parameters.

### Environment overrides (nested profiles)
Nested overrides are supported via environment variables with a predictable mapping. Precedence: per‑call overrides > env overrides > pyproject > SDK defaults.

Scheme:
- Prefix: `AUTO_WORKFLOW_CONNECTORS_`
- Name segment: uppercase connector name, e.g., `POSTGRES`, `S3`, `ADLS2`
- Profile segment: uppercase profile name, e.g., `DEFAULT`, `ANALYTICS`, `LAKE`
- Nested keys: use double underscore `__` to separate path segments

Format: `AUTO_WORKFLOW_CONNECTORS_<NAME>_<PROFILE>__<KEY>__[<SUBKEY>...] = <value>`

Examples:
- Postgres DSN: `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__DSN="secret://env/PG_ANALYTICS_DSN"`
- Postgres discrete + pool:
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__HOST=pg.internal`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__PORT=5432`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__DATABASE=analytics`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__USER=etl`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__PASSWORD=secret://env/PG_ANALYTICS_PASSWORD`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__POOL__MIN_SIZE=1`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__POOL__MAX_SIZE=10`
  - `AUTO_WORKFLOW_CONNECTORS_POSTGRES_ANALYTICS__STATEMENT_TIMEOUT_MS=30000`
- S3 default chain vs static:
  - `AUTO_WORKFLOW_CONNECTORS_S3_DEFAULT__REGION=us-east-1`
  - `AUTO_WORKFLOW_CONNECTORS_S3_DEFAULT__USE_DEFAULT_CREDENTIALS=true`
  - For MinIO/static: `AUTO_WORKFLOW_CONNECTORS_S3_MINIO__ENDPOINT_URL=http://minio.local:9000`
  - `AUTO_WORKFLOW_CONNECTORS_S3_MINIO__CREDENTIALS__ACCESS_KEY_ID=secret://env/MINIO_ACCESS_KEY`
  - `AUTO_WORKFLOW_CONNECTORS_S3_MINIO__CREDENTIALS__SECRET_ACCESS_KEY=secret://env/MINIO_SECRET_KEY`
- ADLS2:
  - `AUTO_WORKFLOW_CONNECTORS_ADLS2_LAKE__ACCOUNT_URL=https://myacct.dfs.core.windows.net`
  - `AUTO_WORKFLOW_CONNECTORS_ADLS2_LAKE__USE_DEFAULT_CREDENTIALS=true`
  - `AUTO_WORKFLOW_CONNECTORS_ADLS2_LAKE__CONNECTION_STRING=...` (alternative to account_url)
  - `AUTO_WORKFLOW_CONNECTORS_ADLS2_LAKE__CREDENTIAL=secret://env/AZURE_STORAGE_SAS` (optional explicit credential)

JSON override (highest precedence for a profile):
- `AUTO_WORKFLOW_CONNECTORS_<NAME>_<PROFILE>__JSON='{"dsn":"...","pool":{"min_size":1}}'`
- When set, this JSON payload overlays the profile after parsing, beating any individual key env vars.

Typing/coercion rules:
- Booleans: `true|false` (case‑insensitive).
- Integers: parsed via `int()`. Floats allowed where relevant.
- Durations: accept strings like `100ms`, `30s`, `5m`; we normalize to seconds or ms depending on the target key.
- Secrets: values starting with `secret://` are resolved via `auto_workflow.secrets`; otherwise treated as literal (still redacted in logs for known secret keys like `password`, `credential`, `secret_access_key`).

Rationale:
- Keeps global `config.py` simple while providing robust, targeted env control for connectors.
- Enables easy containerization and per‑environment overrides without touching `pyproject.toml`.

### Built‑in defaults (safe, production‑leaning)
We will ship sensible defaults per connector. Defaults are applied when a field is not specified in pyproject or env. They never override explicit values.

Defaults precedence recap: built‑in defaults < pyproject < env overrides < per‑call.

Postgres defaults:
- port: 5432
- sslmode: "require" (TLS by default; override only if you must)
- connect_timeout_s: 5
- statement_timeout_ms: 30000
- pool:
  - min_size: 1
  - max_size: 10
  - max_idle_s: 300
- transactions: explicit (no autocommit by default)
- fetch_size: 1000 for server‑side cursors (where used)

S3 defaults:
- use_default_credentials: true (prefer AWS chain over static creds)
- region: None (must come from env/instance/profile if not set)
- endpoint_url: None
- retries:
  - attempts: 5
  - mode: "standard"
- transfer (multipart):
  - multipart_threshold_bytes: 8_388_608  # 8 MiB
  - multipart_chunksize_bytes: 8_388_608   # 8 MiB
  - max_concurrency: 10
- addressing_style: "auto"
- timeouts:
  - connect_s: 5
  - read_s: 60
  - total_s: 120

ADLS2 defaults:
- use_default_credentials: true (prefer Managed/Workload Identity)
- account_url: required (no default)
- retries:
  - attempts: 5
  - backoff: exponential with jitter (100ms..2s)
- upload/download:
  - chunk_size_bytes: 4_194_304  # 4 MiB
  - max_concurrency: 8
- timeouts:
  - connect_s: 5
  - operation_s: 60

Notes:
- These defaults are conservative and production‑oriented (TLS, bounded concurrency, finite timeouts).
- Region/account settings are not assumed; they must be provided or resolvable by the cloud SDK’s default chain.

## Dependencies
- No new default runtime deps. Provide extras in `pyproject.toml`:
  - `connectors-postgres = ["psycopg[binary,pool]>=3.2"]`
  - `connectors-s3 = ["boto3>=1.34"]` (+ optional `aioboto3` for async)
  - `connectors-adls2 = ["azure-storage-blob>=12.27.0", "azure-storage-file-datalake>=12.22.0", "azure-identity>=1.25.1"]`
- Lazy import in `postgres.py/s3.py/adls2.py`. If missing, raise `ImportError` with actionable message.
- Tests: unit tests don’t require SDKs (mock import boundaries). Integration tests are marked and skipped if deps or envs missing.

Note: Current Azure SDKs listed above require Python >= 3.9. This project targets Python 3.12+, so the requirement is satisfied.

### Dependency management & Poetry extras
Connector dependencies are exposed as Poetry extras so users can install only what they need. Heavy SDKs are not added to default deps.

Proposed `pyproject.toml` snippets (illustrative):

```
[tool.poetry.dependencies]
# ... existing deps ...
psycopg = { version = ">=3.2", optional = true, extras = ["binary"] }
psycopg_pool = { version = ">=3.2", optional = true }
boto3 = { version = ">=1.34", optional = true }
azure-storage-blob = { version = ">=12.27.0", optional = true }
azure-storage-file-datalake = { version = ">=12.22.0", optional = true }
azure-identity = { version = ">=1.25.1", optional = true }

[tool.poetry.extras]
connectors-postgres = ["psycopg", "psycopg_pool"]
connectors-s3 = ["boto3"]
connectors-adls2 = ["azure-storage-blob", "azure-storage-file-datalake", "azure-identity"]
connectors-all = ["psycopg", "psycopg_pool", "azure-storage-blob", "azure-storage-file-datalake", "azure-identity", "sqlalchemy"]
```

Install commands:
- Postgres: `poetry install -E connectors-postgres`
- ADLS2: `poetry install -E connectors-adls2`
- All available: `poetry install -E connectors-all`

Runtime behavior:
- Connector modules will lazy‑import their SDKs; if extras aren’t installed, an actionable error is raised with guidance to install the right extra.
- Unit tests mock imports and don’t require extras. Integration tests will be skipped if extras are missing.

## Observability
- Tracing: one span per operation with stable names:
  - `connector.postgres.query`, attributes: db.system, db.name, net.peer.name, statement.type, row_count, error.class
  - `connector.s3.get_object`, attributes: aws.bucket, aws.key, size, range, error.class
  - `connector.adls2.upload_bytes`, attributes: container, path, size
- Metrics: counters and histograms via `metrics_provider`:
  - `<connector>.<op>.count`, `<connector>.<op>.errors`, `<connector>.<op>.latency_ms`
- Events: hook into `logging_middleware`/`events.py` with structured payloads; redact secrets.

## Timeouts & Retries
- Respect per‑call timeout (default from profile config). Use provider‑native timeouts (psycopg `statement_timeout`, boto3 config, Azure retry policies) plus our outer deadline.
- Retry classification via `classify_error` maps provider errors to `Transient|Permanent|Auth|Timeout`.
- Integrate with auto_workflow task retry/cancellation: if task is cancelled or deadline exceeded, abort I/O promptly and propagate `TimeoutError`.
- ADLS2 uses Azure retry policy when available; `retries.attempts` maps to `total_retries`.

## Resource Lifecycle & Concurrency
- Registry caches clients/pools by `(name, profile, config hash)` using weakrefs; no global mutation beyond cache entries.
- All clients are context‑managed; Postgres uses pool with bounded size; S3/ADLS2 clients are thread‑safe as per SDK guidance; provide per‑operation semaphore if needed.
- Provide `ConnectorRegistry.reset()` for tests.

## Security
- No credentials in logs/traces/events; redact via `utils.redact`.
- Support workload identity / IAM roles / MSI where possible; encourage short‑lived creds.
- TLS required by default where applicable; explicit opt‑out not recommended.

## Error Model
- Raise `ConnectorError` subclasses; never leak raw SDK exceptions across public boundary.
- Attach `cause` in exception chaining; include retryable hint.
- Map common codes (e.g., Postgres serialization failures) to `TransientError`.
- ADLS2: map `HttpResponseError` status codes: 401/403 -> Auth, 404 -> NotFound, 408 -> Timeout, 429/5xx -> Transient.

## Performance
- Postgres: pooled connections, prepared statement option (later), server‑side cursors for large result sets.
- S3/ADLS2: multipart uploads for large payloads; streaming reads/writes; configurable chunk sizes; optional gzip.
- Zero‑copy where feasible; avoid loading entire objects into memory unless requested.

## Rollout Plan (phased; Postgres first)
1) Scaffolding
  - Add `auto_workflow/connectors/` with `__init__.py`, `base.py`, `registry.py`, `exceptions.py`, `types.py`, `utils.py` (no external deps yet).
  - Add unit tests for base contracts + registry; wire basic telemetry hooks (no SDK use).
  - Update docs: this feature doc; stub pages under `docs/` (later PR) with “coming soon”.

2) Postgres (first)
  - [x] Implement psycopg3 pool client; query/execute, transaction context, statement timeout.
  - [x] Add streaming iteration (query_iter) for large result sets.
  - [x] Error classification (timeouts, deadlock/serialization as transient, connection reset).
  - [x] Optional ORM helpers (SQLAlchemy engine/session/reflection) behind extra.
  - [x] Registry lazy import and re-registration for factory discovery.
  - [x] Unit tests (hermetic, mocks; no network) and docs updated; coverage ≥ 90%.

3) S3
  - Implement sync client via boto3; basic ops: get/put/list/delete, multipart, streaming.
  - Add metrics/tracing; retries/timeouts via botocore config + outer deadline.
  - Unit tests (mocks) + contract tests; optional integration via real/minio bucket (skipped by default).

4) ADLS2
  - Implement using `azure-storage-file-datalake` (Blob/DFS clients); upload/download/list/delete; streaming.
  - Instrumentation and error mapping; unit tests + optional integration.

5) Async variants (optional, incremental)
  - Provide async clients where SDKs support them (psycopg async, aioboto3, azure‑sdk async).
  - Ensure isolation so sync users are unaffected.

6) Docs & Examples
  - Add `docs/connectors/*.md`; add examples under `examples/` using tasks with connectors.
  - Add migration/usage guide; configuration reference; observability guide.

7) Hardening & Stabilization
  - Fuzz/soak tests; performance baselines; benchmarks where applicable.
  - Finalize API; mark stable.

### Postgres-first notes
- Extras: `connectors-postgres = ["psycopg[binary,pool]>=3.2"]`
- API surface (initial): `query`, `execute`, `executemany`, `transaction()` context, `copy_from`, `copy_to`.
- Statement timeout enforced via server setting and client outer deadline; cancellation propagates.
- Observability: span name `connector.postgres.query|execute|copy_*`, attributes include db.system, db.name, host, statement.type, row_count, error.class.

## Backward Compatibility
- Entirely additive. No existing public API changes. Default behavior unchanged unless a user imports `auto_workflow.connectors`.

## Open Questions / Decisions
- Async scope: initial release ships sync only; async behind extras in a follow‑up.
- Pluggability: future connectors via entry points? We can expose a simple registration API in `registry.py` and consider entry points later.
- Caching policy: default TTL vs LRU by size? Start simple (size‑bounded, no TTL); revisit with metrics.

## Acceptance & Quality Gates
- Follow `agents/BUILDER_AGENT.md`:
  - Ruff passes; formatting consistent.
  - pytest passes; coverage ≥ 92% overall, new code ~100%.
  - Pre‑commit passes.
  - MkDocs build strict.
- Observability tests: assert span names/attributes and metrics for happy/error paths.
- Security review: redaction tests; no secrets in logs.

## Work Items (tracked for implementation PRs)
- [ ] Add connectors scaffolding files + unit tests (no external deps)
- [ ] Add Postgres client (sync) + tests + docs + examples
- [ ] Add S3 client (sync) + tests + docs + examples
- [ ] Add ADLS2 client (sync) + tests + docs + examples
- [ ] Optional: async clients (staged)
- [ ] Update `pyproject.toml` with extras; ensure no default heavy deps
- [ ] Docs pages under `docs/connectors/` + site nav updates
- [ ] Benchmarks (where applicable)

---

This document is the source of truth for the connectors feature scope, API, and rollout. Subsequent PRs should reference this file and update sections as decisions are made and work progresses.

## Testing Strategy (with external dependencies)

We will split tests into hermetic unit tests and opt-in integration tests. CI will run unit tests always; integration tests are gated and skipped unless the environment explicitly enables them.

### Unit tests (always on)
- Location: `tests/connectors/`
- No network calls; provider SDKs are mocked. For Postgres, mock psycopg pool/cursor and raise representative exceptions to test classification and retries.
- Cover:
  - Config/env overlay resolution and secret resolution
  - Error mapping (Transient/Permanent/Auth/Timeout)
  - Timeouts and cancellation propagation (simulate via mocks)
  - Observability: span names/attributes and metrics emitted (using test providers)
  - Resource lifecycle: context manager, idempotent close, registry caching/reset

### Integration tests (opt-in)
- Location: `tests/connectors_integration/`
- Pytest marker: `@pytest.mark.connectors_integration` and sub-marker `postgres`
- Skipped by default unless `AUTO_WORKFLOW_RUN_INTEGRATION_TESTS=1` or connector-specific flag `AUTO_WORKFLOW_POSTGRES_INTEGRATION=1` is set.
- Postgres setup options:
  1) Docker: we provide a `docker-compose.postgres.yml` (or a simple `docker run` command documented) to start a local Postgres 16 with a test database/user.
  2) External: if env variables provide a DSN/host/user/password, tests will connect to that instead.

Environment variables for integration:
- Postgres:
  - `PG_INTEGRATION_DSN` or discrete `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`
  - Optional SSL config if required by environment
- S3 (LocalStack default):
  - `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`, `AWS_REGION=us-east-1`
  - `AWS_ENDPOINT_URL=http://localhost:4566`
  - `S3_TEST_BUCKET=aw-test-bucket`
- ADLS2 (Azurite recommended for local basic ops):
  - `AZURE_STORAGE_ACCOUNT=devstoreaccount1`
  - `AZURE_STORAGE_KEY=Eby8vdM02xNOcqFlqUwJPLlmEtlCD...` (Azurite default)
  - `ADLS2_ACCOUNT_URL=http://127.0.0.1:10000/devstoreaccount1`
  - Note: Azurite DFS support may be limited; tests will skip or xfail unsupported operations. Real Azure account can be used by setting `ADLS2_ACCOUNT_URL` to `https://<acct>.dfs.core.windows.net` and providing a SAS or client secret.

Pytest markers and fixtures:
- Markers:
  - `@pytest.mark.connectors_integration` global marker
  - `@pytest.mark.postgres`, `@pytest.mark.s3`, `@pytest.mark.adls2` sub-markers
- Fixtures:
  - `postgres_url` resolves DSN; `pg_client` yields `PostgresClient`
  - `s3_client_it` yields `S3Client` configured for LocalStack or real AWS, ensures `S3_TEST_BUCKET` exists
  - `adls2_client_it` yields `ADLS2Client` for Azurite/real Azure; creates and cleans a test container

Service setup (documented in repo, optional for local runs):
- Postgres: `docker run --rm -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16`
- S3 via LocalStack: `docker run --rm -p 4566:4566 -e SERVICES=s3 localstack/localstack:latest`
- ADLS2 via Azurite: `docker run --rm -p 10000:10000 mcr.microsoft.com/azure-storage/azurite`

CI strategy:
- Default CI job runs unit tests only.
- Separate opt-in job (nightly/long) spins Postgres/LocalStack/Azurite service containers and runs `pytest -m connectors_integration`.
- Collect logs/artifacts; avoid per-test retries to reduce flakiness masking.

Developer workflow:
- Inner loop: unit tests only (fast, hermetic).
- Before merge or when modifying connector I/O paths: run integration markers for the specific connector(s) locally with containers as needed.

### Native access testing
- Unit tests: ensure native handles are configured correctly (endpoints/credentials/ssl) and that lifecycle rules are enforced (e.g., Postgres `connection()` returns to pool on exit).
- Integration tests: a small number of smoke tests per connector to verify basic operations through native clients (e.g., Postgres `cursor().execute('select 1')`, S3 `boto3_client().list_buckets()`, ADLS2 `filesystem_client(...).get_paths()`), while noting that native calls bypass our wrappers’ observability.

### Caveats and guidance for native access
- Using native handles may bypass our error mapping, retries, and tracing/metrics. Prefer wrapper methods for production workflows.
- If native is required, use within the connector’s context manager to inherit lifecycle and deadlines. For Postgres, always prefer `connection()` context to avoid leaking connections.
- Do not close underlying shared clients/pools directly; closing is connector‑owned. For Postgres, closing a checked‑out connection via context manager is expected; the pool remains managed by the connector.
