# API Reference (Manual Overview)

> For a generated reference, integrate mkdocs-material + mkdocstrings or Sphinx in the future. This page summarizes the stable public surface.

## Public Exports (`auto_workflow.__all__`)
| Symbol | Type | Description |
|--------|------|-------------|
| task | decorator | Define a TaskDefinition |
| TaskDefinition | class | Task metadata & execution logic |
| flow | decorator | Define a Flow |
| Flow | class | Flow execution + export methods |
| get_context | function | Access current RunContext inside tasks |
| fan_out | function | Declare static or dynamic fan-out |
| FailurePolicy | enum-like | Failure policy constants |
| subscribe | function | Register event subscriber |

## TaskDefinition
Important attributes: `name`, `retries`, `retry_backoff`, `retry_jitter`, `timeout`, `cache_ttl`, `persist`, `priority`, `run_in`.

### Methods
- `run(*args, **kwargs)` (async): internal coroutine used by scheduler.
- `__call__(*args, **kwargs)`: build-time registration (within a flow) or immediate execution (outside a flow).

## Flow
Methods:
- `run(..., failure_policy, max_concurrency, params)` -> executes flow.
- `describe()` -> JSON-serializable graph spec.
- `export_dot()` / `export_graph()` -> Graph representations.

## fan_out(task_def, iterable, max_concurrency=None)
- If iterable is a concrete collection, returns list of task invocations (static mapping).
- If iterable is a TaskInvocation (upstream result placeholder), returns DynamicFanOut placeholder.

## Events
See [Middleware & Events](middleware-events.md) for list.

## Configuration
See [Configuration](configuration.md).

## Error Types (from exceptions module)
- `RetryExhaustedError`
- `TimeoutError`
- `TaskExecutionError`
- `AggregateTaskError`

## Tracing
Replace tracer with `set_tracer(custom_tracer)` where custom tracer exposes `async def span(name, **attrs)` context manager.

## Secrets
`secret(key)` fetches credential via active provider.

## Version Compatibility
APIs documented here are considered MVP-stable; breaking changes will be noted in changelog pre-1.0 with migration notes.
