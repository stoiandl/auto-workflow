# Getting Started

This page gives you a structured path from installation to building production-ready flows.

## 1. Install
Install with `pip install auto-workflow` or see [Quickstart](quickstart.md#installation) for development setup.

## 2. Learn Core Primitives
1. Read [Tasks](concepts/tasks.md)
2. Read [Flows](flows.md)
3. Skim [Dynamic Fan-Out](dynamic-fanout.md) for mapping patterns

## 3. Build Your First Flow
Follow the minimal example in [Quickstart](quickstart.md#define-tasks-flow). Run it and inspect with `describe()` / `export_dot()`.

## 4. Add Reliability
Configure retries, backoff, and timeouts: [Retries & Failures](retries-timeouts-failure.md)

## 5. Optimize Execution
- Use `priority` to schedule important tasks earlier
- Apply `max_concurrency` if your environment has resource limits

## 6. Manage Data
Decide per task:
- Large payload? -> `persist=True` (see [Caching & Artifacts](caching-artifacts.md))
- Expensive but deterministic? -> `cache_ttl=...`

## 7. Observe & Debug
- Subscribe to events (see [Middleware & Events](middleware-events.md))
- Add logging middleware for structured logs
- Export a DOT graph for visualization

## 8. Handle Secrets
Integrate your secrets provider per [Secrets](secrets.md) before embedding credentials.

## 9. Extend
Need custom caching, tracing, or metrics? See [Extensibility](extensibility.md).

## 10. Prepare for Production
Checklist:
- [ ] All tasks idempotent or guarded by cache
- [ ] Retries set on transient operations
- [ ] Timeouts defined for network-bound tasks
- [ ] Artifact persistence for large objects
- [ ] Events subscribed for alerts / metrics exported
- [ ] Flow graph exported & documented

## Navigation Tips
- Use the left sidebar (MkDocs) to jump sections.
- Each page has an auto-generated table of contents (right side if theme supports) due to `toc` extension.
- Start broad (Quickstart) then dive deeper (API Reference) as needed.

## Common Next Questions
| Goal | Where to Look |
|------|---------------|
| "How do I dynamically map tasks?" | [Dynamic Fan-Out](dynamic-fanout.md) |
| "How do I skip recomputation?" | [Caching & Artifacts](caching-artifacts.md) |
| "How do I trace performance?" | [Observability](observability.md) |
| "Where is the public API list?" | [API Reference](api-reference.md) |

---
If anything feels missing, open an issue or PR—this page should remain the fastest on-ramp.
