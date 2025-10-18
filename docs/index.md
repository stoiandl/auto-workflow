# auto-workflow Documentation

Welcome to the comprehensive documentation for `auto-workflow`, a lightweight, developer-first task & flow orchestration engine.

Use the navigation to explore topics or start with the [Quickstart](quickstart.md).

## Core Guarantees
- Pure-Python authoring (no external DB or daemon required)
- Async-first runtime with optional thread/process execution
- Explicit dynamic fan-out (controlled, introspectable)
- Deterministic DAG build with runtime expansion support
- Pluggable persistence (artifacts, result cache), metrics & tracing hooks

## Feature Matrix (Implemented)
| Capability | Status |
|------------|--------|
| Task decorator (`@task`) | ✅ |
| Flow decorator (`@flow`) | ✅ |
| Async/thread/process execution | ✅ |
| Retries + backoff + jitter | ✅ |
| Timeouts | ✅ |
| Failure policies (fail-fast, continue, aggregate) | ✅ |
| Dynamic fan-out (single-level reliable) | ✅ |
| Nested dynamic (experimental) | ⚠️ Partial (not hardened) |
| Result cache (memory + filesystem) | ✅ |
| Artifact store (memory + filesystem) | ✅ |
| Priority scheduling | ✅ |
| Cancellation | ✅ |
| Graph export (DOT + JSON) | ✅ |
| Tracing scaffold | ✅ |
| Metrics (in-memory) | ✅ |
| Secrets providers (env, static mapping, dummy vault) | ✅ |
| CLI (run/describe/list) | ✅ |
| Benchmark harness (internal) | ✅ |
| Connectors (Postgres, SQLAlchemy helpers) | ✅ |

## Roadmap Highlights
See [Extensibility](extensibility.md) for upcoming work (OpenTelemetry exporter, advanced secrets, UI, packaging).

## Getting Help
If something is unclear or missing, open an issue with a minimal reproducible example.

Useful links:
- Connectors overview and examples: [Connectors](connectors.md)
- Local Postgres testing via Docker Compose: [Testing](testing.md)
