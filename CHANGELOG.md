# Changelog

All notable changes to this project will be documented in this file.

This project follows Keep a Changelog and Semantic Versioning. Pre‑1.0 releases may contain breaking changes in minor versions.

## [Unreleased]
### Planned
- Executor plugins and additional failure policies
- Richer DAG visualizations and export formats
- More cache/artifact backends and configuration surface
- Extended metrics/tracing providers and middleware library

## [0.1.2] - 2025-10-12
### Added
- Comprehensive tests for dynamic fan-out graph representation:
	- Simple dynamic mapping, nested fan-out (2–3 levels), sibling fan-outs merged downstream,
		and multiple consumers sharing the same fan-out.

### Changed
- `Flow.describe()` now models dynamic fan-outs explicitly as barrier nodes (`fanout:{n}`),
	deduplicates multi-consumers, and propagates transitive dependencies so downstream nodes
	correctly reference all relevant fan-out barriers.
- `Flow.export_dot()` renders fan-out barriers as diamond-shaped nodes labeled `fan_out(task)`
	and wires `source -> fanout -> consumer`, including fanout-of-fanout chains.

### Fixed
- Incorrect/missing dynamic fan-out edges in `describe()`/`export_dot()` for nested mapping and
	multi-branch scenarios; graphs now reflect true execution ordering without duplicate edges.

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
