# ADLS2 Connector - End-to-End Implementation Plan

Status: Planning (ready to implement)
Owner: TBD
Target branch: feat/adls2-connector

## Scope
Implement the Azure Data Lake Storage Gen2 (ADLS2) connector as specified in `features/production-connectors.md`, following `agents/BUILDER_AGENT.md` rules. Deliver a fully tested, documented, and optional-dependency-based client with consistent API and observability.

## Deliverables
- Code:
  - `auto_workflow/connectors/adls2.py` (sync client, lazy imports, error mapping, observability)
  - Integration into `auto_workflow.connectors` registry (factory + defaults)
- Tests (unit, hermetic):
  - `tests/connectors/test_adls2_unit.py` covering API, error mapping, timeouts, observability, config/env overlay
  - Optional integration tests skeleton (skipped by default)
- Docs:
  - Update `docs/connectors.md` section for ADLS2 usage and configuration
  - Example snippet under `examples/` if useful (small)
- Packaging:
  - Poetry extras in `pyproject.toml`: `connectors-adls2` with `azure-storage-blob`, `azure-storage-file-datalake`, `azure-identity`

## API Surface (as per spec)
Class: `ADLS2Client`
- Lifecycle: context manager, `close()`, `is_closed()`
- Upload/Download:
  - `upload_bytes(container: str, path: str, data: bytes | IO[bytes], *, content_type: str | None = None, metadata: dict[str,str] | None = None, overwrite: bool = True, chunk_size: int | None = None, timeout: float | None = None) -> str` (etag)
  - `download_bytes(container: str, path: str, *, start: int | None = None, end: int | None = None, timeout: float | None = None) -> bytes`
  - `download_stream(container: str, path: str, *, chunk_size: int | None = None, timeout: float | None = None) -> Iterator[bytes]`
- Listing & existence:
  - `list_paths(container: str, prefix: str | None = None, *, recursive: bool = True, timeout: float | None = None) -> Iterator[PathInfo]`
  - `exists(container: str, path: str, *, timeout: float | None = None) -> bool`
- Delete & directories:
  - `delete_path(container: str, path: str, *, recursive: bool = False, timeout: float | None = None) -> None`
  - `make_dirs(container: str, path: str, *, exist_ok: bool = True, timeout: float | None = None) -> None`
- Native access:
  - `datalake_service_client() -> azure.storage.filedatalake.DataLakeServiceClient`
  - `filesystem_client(container: str) -> azure.storage.filedatalake.FileSystemClient`

Types:
- `PathInfo = dict[str, Any]` with `container`, `path`, `is_directory`, `size`, `last_modified`, `etag`
- Config: `ADLS2Config` (already exists) with defaults per spec

## Error Model & Mapping
Map Azure SDK exceptions to `ConnectorError` hierarchy:
- `azure.core.exceptions.ServiceRequestError`, `ReadTimeoutError` -> `TimeoutError`
- `azure.core.exceptions.ClientAuthenticationError` -> `AuthError`
- `azure.core.exceptions.ResourceNotFoundError` -> `NotFoundError`
- `azure.core.exceptions.ServiceResponseError`, `HttpResponseError` (5xx) -> `TransientError`
- Others -> `PermanentError`
Include original exception via exception chaining.

## Timeouts & Retries
- Configure inner Azure SDK retry policy via client options (attempts/backoff from `ADLS2Config.retries`).
- Apply outer deadline with `operation_s` using a helper (e.g., `utils.deadline`, or `asyncio` if available; for sync, use wall-clock checks and per-call client timeouts).
- Propagate cancellation/timeout promptly, ensuring SDK calls are aborted where possible.

## Observability
- Tracing spans per operation: `connector.adls2.<op>` with attributes: `azure.account`, `container`, `path`, `bytes`, `chunk_size`, `attempts`, `error.class`.
- Metrics: increment counters and record latency histograms via `metrics_provider`.
- Events: structured logs with redacted values (`credential`, SAS tokens).

## Configuration & Secrets
- Source `ADLS2Config` from `auto_workflow.config` under `connectors.adls2.<profile>` with env overlays per spec, resolving `credential` via `auto_workflow.secrets` if it starts with `secret://`.
- Support `use_default_credentials` to use `DefaultAzureCredential` when `credential` is not provided.

## Implementation Steps
1) Factory & registration
   - Add `adls2.py` with `client(profile: str = "default") -> ADLS2Client` and factory registered in `registry`.
   - Implement config resolution + defaults + env overlay using existing helpers.

2) SDK wiring (lazy import)
   - Import `DataLakeServiceClient`, `FileSystemClient`, `ContentSettings` from Azure SDK inside functions.
   - If import fails, raise `ImportError` with guidance: `poetry install -E connectors-adls2`.

3) Client implementation
   - Hold a `DataLakeServiceClient` instance (thread-safe).
   - Implement `filesystem_client(container)`; for file ops, use `FileSystemClient.get_file_client` -> `DataLakeFileClient`.
   - Upload: if bytes-like, stage blocks via `upload_data` with overwrite flag; set content type via `ContentSettings`.
   - Download: use `read_file()` to get bytes; stream via `download_file().chunks()`.
   - List: `FileSystemClient.get_paths(name_starts_with=prefix, recursive=recursive)` yielding normalized `PathInfo`.
   - Exists: use `get_file_client`/`get_directory_client` and `get_file_properties` try/except.
   - Delete: `delete_file` or `delete_directory` depending on `recursive`.
   - Directories: `create_directory(path)`; handle `ResourceExistsError` when `exist_ok`.

4) Error mapping layer
   - Centralize exception translation in a decorator/helper `wrap_errors(op_name)`.

5) Observability
   - Wrap each public method in tracing/metrics; redact sensitive fields.

6) Tests (unit)
   - Mock Azure SDK classes; assert calls, error mapping, timeouts behavior (simulated), and observability signals.
   - Config/env overlay tests specific to ADLS2.

7) Docs
   - Update `docs/connectors.md` with ADLS2 install instructions (`poetry install -E connectors-adls2`), example usage, config, and env overrides.

8) Optional integration tests (skipped by default)
   - Skeleton under `tests/connectors_integration/test_adls2_integration.py` using environment variables; mark and skip unless enabled.

## Risks & Mitigations
- SDK differences between Blob and DFS: prefer `azure-storage-file-datalake` for filesystem semantics; fallback ops may use blob client under the hood as needed.
- Azurite DFS limitations: integration tests guarded by markers and skips.
- Large payloads: implement chunked streaming with configurable `chunk_size` and bounded concurrency (initially sync, conservative defaults).

## Acceptance Criteria
- All gates pass locally: ruff, tests (>=92% overall), pre-commit, mkdocs strict.
- Clear ImportError guidance when extras missing.
- Public API and behavior match the feature spec.
- Docs updated with usage and configuration.

## Next PR after this plan
- Implement `auto_workflow/connectors/adls2.py`
- Add unit tests and docs updates
- Wire registry
- Optional: examples and integration test skeleton
