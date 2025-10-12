<div align="center">

<picture>
	<source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/stoiandl/auto-workflow/main/assets/logo.svg" />
		<img alt="auto-workflow" src="https://raw.githubusercontent.com/stoiandl/auto-workflow/main/assets/logo.svg" width="560" />
</picture>

# auto-workflow

[![CI](https://github.com/stoiandl/auto-workflow/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/stoiandl/auto-workflow/actions/workflows/ci.yml)
[![Docs build](https://github.com/stoiandl/auto-workflow/actions/workflows/docs.yml/badge.svg?branch=main&event=push)](https://github.com/stoiandl/auto-workflow/actions/workflows/docs.yml)
[![Coverage Status](https://img.shields.io/codecov/c/github/stoiandl/auto-workflow/main?logo=codecov&label=coverage)](https://app.codecov.io/gh/stoiandl/auto-workflow)
[![PyPI](https://img.shields.io/pypi/v/auto-workflow.svg?logo=pypi&label=PyPI)](https://pypi.org/project/auto-workflow/)
[![Downloads](https://static.pepy.tech/badge/auto-workflow/month)](https://pepy.tech/project/auto-workflow)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://stoiandl.github.io/auto-workflow/) [![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

_A lightweight, zero-bloat, developer‑first workflow & task orchestration engine for Python._

**Status:** Alpha (APIs stabilizing). **Goal:** Production‑grade minimal core with pluggable power features.

</div>

## Quick links

- Docs (GitHub Pages): https://stoiandl.github.io/auto-workflow/
- Repository: https://github.com/stoiandl/auto-workflow


## Table of Contents
1. [Why Another Orchestrator?](#why-another-orchestrator)
2. [Philosophy & Design Principles](#philosophy--design-principles)
3. [Feature Overview](#feature-overview)
4. [Quick Start](#quick-start)
5. [Core Concepts](#core-concepts)
6. [Execution Modes](#execution-modes)
7. [Building Flows & DAGs](#building-flows--dags)
8. [Dynamic Fan‑Out / Conditional Branching](#dynamic-fan-out--conditional-branching)
9. [Result Handling, Caching & Idempotency](#result-handling-caching--idempotency)
10. [Retries, Timeouts & Failure Semantics](#retries-timeouts--failure-semantics)
11. [Hooks, Events & Middleware](#hooks-events--middleware)
12. [Configuration & Environment](#configuration--environment)
13. [Observability (Logging, Metrics, Tracing)](#observability-logging-metrics-tracing)
14. [Extensibility Roadmap](#extensibility-roadmap)
15. [Security & Isolation Considerations](#security--isolation-considerations)
16. [Comparison with Airflow & Prefect](#comparison-with-airflow--prefect)
17. [Project Structure (Proposed)](#project-structure-proposed)
18. [FAQ](#faq)
19. [Roadmap](#roadmap)
20. [Contributing](#contributing)
21. [Versioning & Stability](#versioning--stability)
22. [License](#license)
 23. [Examples Overview](#examples-overview)


## Why Another Orchestrator?
Existing platforms (Airflow, Prefect, Dagster, Luigi) solve orchestration at scale—but often at the cost of:


`auto-workflow` targets a different sweet spot:

> **Be the simplest way to express, execute and evolve complex, dynamic task graphs directly in Python—locally first—while remaining extensible to production constraints.**

Core values: **No mandatory DB**, **no daemon**, **no CLI bureaucracy**, **opt‑in persistence**, **first-class async**, **predictable concurrency**, **explicit data flow**.


## Philosophy & Design Principles
| Principle | Description |
|-----------|-------------|
| Minimal Core | Ship only primitives: Task, Flow (DAG), Executor, Runtime. Everything else is a plugin or optional layer. |
| Python Native | Flows are plain Python; no YAML DSL or templating required. |
| Deterministic by Default | Task graph shape should be reproducible given the same inputs. Explicit APIs for dynamic fan‑out. |
| Composable | Tasks are small units; flows can nest; subgraphs are reusable. |
| Extensible | Storage adapters, retry policies, and event sinks are pluggable via clean interfaces. |
| Progressive Adoption | Use it as a simple task runner first; layer complexity only when needed. |
| Observability Hooks | Logging / metrics / tracing surfaces are unified and optional. |
| Zero Hidden State | No implicit global registry; registration is explicit or decorator‑driven with clear import semantics. |
| Performance Conscious | Support high‑throughput local pipelines via async & thread/process pools with minimal overhead. |


## Feature Overview
Planned / partially implemented capabilities:



## Quick Start
Install from PyPI:

```bash
pip install auto-workflow
```

Or for local development with Poetry:

Run tests locally:

```bash
poetry run pytest --cov=auto_workflow --cov-report=term-missing
```

### Define Tasks
```python
from auto_workflow import task, flow

@task
def load_numbers() -> list[int]:
	return [1, 2, 3, 4]

@task
def square(x: int) -> int:
	return x * x

@task
def aggregate(values: list[int]) -> int:
	return sum(values)

@flow
def pipeline():
	nums = load_numbers()
	# Fan-out map (dynamic child tasks)
	squared = [square(n) for n in nums]  # Under the hood becomes dynamic tasks
	return aggregate(squared)

if __name__ == "__main__":
	result = pipeline.run()
	print(result)
```

### CLI
```bash
python -m auto_workflow run path.to.pipeline:pipeline
```

List and describe flows:

```bash
python -m auto_workflow list path.to.module
python -m auto_workflow describe path.to.pipeline:pipeline
```

If installed via pip, a console script is also available:

```bash
auto-workflow run path.to.pipeline:pipeline
```


## Core Concepts
### Task
Unit of work: a pure (or side-effecting) Python callable that declares inputs & returns outputs. Decorated with `@task` for metadata: name, retries, timeout, tags, cache key fn.

### Flow (or Pipeline)
Container for a DAG of tasks. May be defined with `@flow` decorator wrapping a function whose body builds the dependency graph during invocation. Supports nested flows.

### DAG
Directed acyclic graph where edges represent data or control dependencies. Construction is implicit via using outputs of tasks as inputs to other tasks (like Prefect) but without global mutable state.

### Execution Context
Available via `from auto_workflow.context import get_context()` inside a task for run metadata, logger, parameters.

### Parameters
Flow-level runtime parameters passed at `.run(params={...})` enabling configurability without environment variables.

### Artifacts
Structured results (maybe large) that can optionally be stored externally; default is in‑memory pass‑through.


## Execution Modes
Tasks run using one of three simple modes:

Mode selection:


## Building Flows & DAGs
Two equivalent approaches (both may be supported):

1. **Imperative Functional** (Python execution builds nodes):
   ```python
   @flow
   def my_flow():
	   a = task_a()
	   b = task_b(a)
	   c = task_c(a, b)
	   return c
   ```
2. **Explicit Builder** (defer evaluation):
   ```python
   from auto_workflow import FlowBuilder
   fb = FlowBuilder(name="my_flow")
   a = fb.task(task_a)
   b = fb.task(task_b, a)
   c = fb.task(task_c, a, b)
   flow = fb.build()
   flow.run()
   ```


## Dynamic Fan-Out / Conditional Branching
Dynamic forks are explicit to preserve introspection & safety:
```python
@task
def split_batches(data: list[int]) -> list[list[int]]: ...

@task
def process_batch(batch: list[int]) -> int: ...

@task
def combine(results: list[int]) -> int: return sum(results)

@flow
def batch_flow(data: list[int]):
	batches = split_batches(data)
	results = fan_out(process_batch, iterable=batches, max_concurrency=8)
	return combine(results)

@flow
def conditional_flow(flag: bool):
	a = task_a()
	if flag:
		b = task_b(a)
	else:
		b = task_c(a)
	return b
```
`fan_out` constructs a bounded dynamic subgraph; a future `fan_in` utility may allow explicit barrier semantics.


## Result Handling, Caching & Idempotency
Strategies (planned):

Example (concept):
```python
@task(cache_ttl=3600)
def expensive(x: int) -> int:
	return do_work(x)
```


## Retries, Timeouts & Failure Semantics
Per-task configuration:
```python
@task(retries=3, retry_backoff=2.0, retry_jitter=0.3, timeout=30)
def flaky(): ...
```
Failure policy options (proposed):


## Hooks, Events & Middleware
Lifecycle hook points:

Middleware chain (similar to ASGI / HTTP frameworks):
```python
def timing_middleware(next_call):
	async def wrapper(task_ctx):
		start = monotonic()
		try:
			return await next_call(task_ctx)
		finally:
			duration = monotonic() - start
			task_ctx.logger.debug("task.duration", extra={"ms": duration*1000})
	return wrapper
```

Event bus emission (planned): structured events -> pluggable sinks (stdout logger, OTLP exporter, WebSocket UI).


## Configuration & Environment
Minimal first-class configuration (future `pyproject.toml` block):
```toml
[tool.auto_workflow]
default-executor = "async"
log-level = "INFO"
max-dynamic-tasks = 2048
```
Environment overrides are available for documented keys (see docs/configuration.md).


## Observability (Logging, Metrics, Tracing)
Implemented surface + extensions you can plug in:


## Extensibility Roadmap
| Extension | Interface | Status |
|-----------|-----------|--------|
| Executor plugins | `BaseExecutor` | Planned |
| Storage backend | `ArtifactStore` | Planned |
| Cache backend | `ResultCache` | Planned |
| Metrics provider | `MetricsProvider` | Planned |
| Tracing adapter | `Tracer` | Planned |
| Retry policy | Strategy object | Planned |
| Scheduling layer | External module | Backlog |
| UI / API | Optional service | Backlog |


## Security & Isolation Considerations


## Comparison with Airflow & Prefect
| Aspect | auto-workflow | Airflow | Prefect |
|--------|---------------|---------|---------|
| Requires DB / Scheduler | No (local in-process) | Yes | No (cloud optional) |
| First-class async | Yes (core) | Limited | Yes |
| Dynamic DAG at runtime | Explicit fan-out | Limited / brittle | Supported |
| Footprint | Minimal deps | Heavy | Moderate |
| UI bundled | No (optional) | Yes | Yes |
| Plugin surface | Lean, Pythonic | Large | Large |
| Setup time | Seconds | Minutes+ | Minutes |


## Project Structure (Proposed)
```
auto_workflow/
  __init__.py
  tasks.py          # @task decorator & Task definition
  flow.py           # Flow abstraction & @flow decorator
  dag.py            # Internal DAG model
	execution.py
	base.py
	async_executor.py
	thread_executor.py
  runtime/
	context.py
	scheduler.py     # Lightweight topological / async scheduler
  middleware/
  events/
  caching/
  storage/
  observability/
tests/
examples/
docs/
```


## FAQ
**Q: Is persistence required?**  No—default run is ephemeral in memory.

**Q: Can I dynamically create thousands of tasks?** Yes, but bounded; guardrails (`max-dynamic-tasks`) will protect runaway expansion.

**Q: How are circular dependencies prevented?** DAG builder performs cycle detection before execution.

**Q: Do I need decorators?** No; you can manually wrap callables into Tasks if you prefer pure functional style.

**Q: How does it serialize arguments across processes?** Planned fallback: cloudpickle; user can register custom serializer.

**Q: Scheduling / cron?** Out of core scope—provide a thin adapter so external schedulers (cron, systemd timers, GitHub Actions) can invoke flows.


## Roadmap


## Examples Overview
Explore runnable examples in `examples/` (also rendered in the online docs):

| File | Concept Highlights |
|------|--------------------|
| `data_pipeline.py` | Basic ETL flow with persistence & simple mapping |
| `concurrent_priority.py` | Priority scheduling & mixed async timings |
| `dynamic_fanout.py` | Runtime fan-out expansion and aggregation |
| `retries_timeouts.py` | Retry + timeout interplay demonstration |
| `secrets_and_artifacts.py` | Secrets provider & artifact persistence usage |
| `tracing_custom.py` | Custom tracer capturing spans & durations |

Run any example:
```bash
python examples/tracing_custom.py
```

For more narrative documentation see the [Examples page](https://stoiandl.github.io/auto-workflow/examples/).


## Contributing
Contributions are welcome once the core API draft solidifies. Until then:
1. Open an issue to discuss proposals.
2. Keep changes atomic & well-tested.
3. Adhere to Ruff formatting & lint rules (pre-commit enforced).
4. Add or update examples & docs for new features.

Planned contribution guides: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.


## Versioning & Stability
Pre-1.0: **Breaking changes can occur in minor releases**. After 1.0 we will follow [Semantic Versioning](https://semver.org/).

Migration notes will be maintained in `CHANGELOG.md` (to be added).


## License
This project is licensed under the GNU General Public License v3.0. See `LICENSE` for details. If you need alternate licensing, open an issue to discuss.


## Legal / Disclaimer
This project is experimental; do not deploy to critical production paths until a 1.0 release is tagged. Feedback welcomed to refine design decisions.


Happy orchestrating! 🚀

Note on releases: Publishing to PyPI is performed by CI when a tag `vX.Y.Z` is pushed to the repository. We use PyPI Trusted Publishing; no local uploads are required.
