# Changelog

All notable changes to this project will be documented in this file.

This project follows Keep a Changelog and Semantic Versioning. Pre‑1.0 releases may contain breaking changes in minor versions.

## [0.1.2] - Unreleased
### Added
- Connectors: Postgres client (psycopg3 pool-backed) behind optional extras with:
	- Query/execute/executemany, transaction context, statement timeouts, streaming via `query_iter`
	- SQLAlchemy helpers: `sqlalchemy_engine`, `sqlalchemy_sessionmaker`, `sqlalchemy_session`, `sqlalchemy_reflect`
	- Robust error classification (timeouts, transient deadlocks/serialization, permanent)
	- Registry lazy import and re-registration for already-imported modules
	- Comprehensive unit tests with hermetic fakes (no network)
- Shared environment overlay utilities (`auto_workflow.env_overrides`) with JSON overlay precedence,
	type coercions, and secret resolution; connector wrapper added and covered by tests
- VS Code tasks: Poetry-powered gates and formatter tasks for consistent local runs
- Documentation: Postgres connector usage, extras installation, SQLAlchemy examples, streaming
- CLI validation: `--failure-policy` choices enforced; friendly errors for bad module/object paths; reject non-positive `--max-concurrency`.
 - Postgres convenience methods: `query_one`, `query_value` for ergonomic reads.
 - Postgres pool tuning passthrough: supports `min_size`, `max_size`, `timeout` when available in `psycopg_pool`.
 - Conninfo `application_name` support for improved DB observability.
 - Auth error mapping: common authentication failures now raise `AuthError`.
 - Documentation updates: end-to-end Postgres example (tasks + flow), pool lifecycle guidance, and a full environment variables inventory.
 - ADLS2 connector (Azure Data Lake Storage Gen2) behind optional extras with:
 	- Upload/download bytes and streaming, list paths, exists, delete, and make_dirs
 	- Error classification (timeouts, auth failures, not found, transient vs permanent) with HttpResponseError status mapping
 	- Lazy imports and clear ImportError guidance for missing extras
 	- Registry integration and unit tests with hermetic fakes; mocked integration tests with flows/fan-outs
 	- Content type support via Azure Blob ContentSettings in uploads; chunk_size passthrough
 	- Example `examples/adls_csv_flow.py` demonstrating container creation, CSV write/read, and cleanup
### Changed
- CI: Ensure connector extras are installed (use `connectors-all`); spin up Postgres via Docker Compose for integration tests; wait script and DSN exported in the job
- CI: Add Ruff format check alongside lint; upload coverage to Codecov after tests
- Postgres connector: initialize `psycopg_pool.ConnectionPool` with `open=True` to avoid deprecation warnings; fall back without `open` for test doubles
 - Postgres transactions: all operations inside `transaction()` now run on the same connection; nested transactions do not issue nested `BEGIN/COMMIT`.
 - SQLAlchemy integration: cache default engine/sessionmaker and dispose engine on `close()`.
 - sslmode handling aligned: include only when explicitly configured (conninfo and SQLAlchemy URL).
 - FileSystemArtifactStore no longer keeps duplicate in-memory copies; writes/reads directly to disk, reducing memory footprint.
 - Scheduler fail-fast path now proactively cancels in-flight tasks before raising, improving determinism.
 - `Flow.describe()` now models dynamic fan-outs explicitly as barrier nodes (`fanout:{n}`),
	deduplicates multi-consumers, and propagates transitive dependencies so downstream nodes
	correctly reference all relevant fan-out barriers.
 - `Flow.export_dot()` renders fan-out barriers as diamond-shaped nodes labeled `fan_out(task)`
	and wires `source -> fanout -> consumer`, including fanout-of-fanout chains.
### Fixed
- COPY streaming compatibility and robust fallbacks for file-like vs iterable inputs in `copy_to`/`copy_from`
- SQLAlchemy helpers accept DSNs with legacy `postgres://` and apply appropriate connect_args
- Flow sequencing improvements to ensure setup tasks run before returned concurrent tasks (preserving concurrency semantics)
- Artifact store FS backend test coverage with `artifact_serializer=json`.
- Fail-fast cancellation test ensuring pending tasks are cancelled before error propagation.
- Comprehensive tests for dynamic fan-out graph representation:
	- Simple dynamic mapping, nested fan-out (2–3 levels), sibling fan-outs merged downstream,
		and multiple consumers sharing the same fan-out.
- `AGENT_INSTRUCTIONS.md`: a stricter, end-to-end guide tailored for automated agents contributing to this repo (one-scope PRs, docs/README/changelog updates, 100% coverage for new code, pre-commit, and CI parity commands).

 - Ruff lint improvements in SQLAlchemy session helper (use `contextlib.suppress`).
 - ADLS2 example failures addressed by ensuring container creation and aligning UTC usage; example notes added to docs.
 - Incorrect/missing dynamic fan-out edges in `describe()`/`export_dot()` for nested mapping and
	multi-branch scenarios; graphs now reflect true execution ordering without duplicate edges.
 - DOT export now suppresses direct edges from original sources when a dynamic `fan_out` barrier
	 mediates the dependency. Graphs correctly render `source -> fanout -> ... -> consumer` without
	 bypass edges (e.g., no `load_numbers -> aggregate` when fan-outs are present).

## [0.1.1] - 2025-10-12
### Fixed
- **BREAKING FIX**: Corrected documentation examples that showed invalid `[square(n) for n in nums]` pattern which doesn't work since `nums` is a `TaskInvocation`, not an iterable
- All examples now correctly use `fan_out(square, nums)` for dynamic fan-out
- Removed references to non-existent `FlowBuilder` API
- Updated installation instructions with correct GitHub repository URL
- Fixed feature status from "planned" to accurate implementation status
- Corrected API reference documentation to match actual exports
- Updated configuration and extensibility documentation

## [0.1.0] - 2025-10-12
Initial alpha release.

### Added
- Core workflow runtime
	- `@task` decorator and `TaskDefinition` with:
		- retries, exponential backoff, jitter, timeout
		- caching hooks (`cache_ttl`, `cache_key_fn`)
		- tagging and priority
		- execution targets: `async`, `thread`, `process` (process via `cloudpickle`)
		- optional persistence flag (`persist`) for artifact store handoff
	- Task execution with tracing spans and event emissions (`task_retry`), never blocking the event loop for sync work by default (threads).
	- Flow API (`@flow`, `Flow`) with DAG construction and `describe()` for graph introspection.
	- Dynamic fan-out via `fan_out(...)` helper to create bounded dynamic subgraphs.
	- Lightweight scheduler with `FailurePolicy` support (configurable from CLI).
	- Execution context (`get_context`) and lifecycle (`lifecycle.shutdown`) utilities.
	- Event bus (`emit`, `subscribe`) and middleware surface for cross-cutting concerns.
	- Structured logging middleware with pretty console logging by default, opt-out via env.
	- Tracing and metrics provider interfaces (`get_tracer`, `MetricsProvider` scaffolding).
	- Artifacts and caching scaffolding; secrets provider surface.

- CLI
	- `python -m auto_workflow` supporting:
		- `run module:flow_object` (with `--failure-policy`, `--max-concurrency`, `--params`)
		- `describe module:flow_object` (JSON graph description)
		- `list module` (enumerate `Flow` objects)
	- Console script entry point `auto-workflow` mirroring module CLI.

- Packaging & distribution
	- PEP 621/Poetry metadata, minimal runtime deps.
	- PEP 561 typing marker (`auto_workflow/py.typed`) and `Typing :: Typed` classifier.
	- `__version__` exposed via `importlib.metadata`.
	- Console script via `[tool.poetry.scripts]` and module entry point `__main__.py`.
	- Classifiers include Python 3.12, Development Status :: 3 - Alpha, Environment :: Console.

- Documentation & examples
	- MkDocs site with Material theme and pages for: getting started, quickstart, flows, tasks, dynamic fan-out, retries/timeouts/failure, caching/artifacts, configuration, secrets, observability, middleware/events, extensibility, examples, and API reference stub.
	- Examples demonstrating concurrency/priority, dynamic fan-out, retries/timeouts, tracing customization, secrets and artifacts, and a basic data pipeline.

- CI/CD
	- CI workflow: lint (Ruff), unit tests (pytest), coverage (branch), Codecov upload.
	- Docs workflow: build and publish to GitHub Pages on main.
	- Release workflow `pypi-flow.yml` (PyPI Trusted Publishing):
		- Tag-driven builds on `v*`.
		- Publish to TestPyPI for `-rc` tags; publish to PyPI for final tags.

### Changed
- README updated for PyPI readiness:
	- Added `pip install auto-workflow` and minimal CLI usage.
	- Switched logo to absolute URL for PyPI rendering.
	- Clarified project status to Alpha.
- Packaging improvements:
	- Added console script `auto-workflow`.
	- Included typing marker and expanded classifiers.

### Fixed
- Import startup made robust: logging middleware registration wrapped to avoid import-time failures.

### Internal
- Ruff lint/format configuration and enforced checks.
- Pytest configuration with markers and coverage ≥ 90% gate.
- Coverage configuration (omit docs/examples/site), branch coverage enabled.
