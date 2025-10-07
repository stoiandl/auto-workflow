# Retries, Timeouts & Failure Handling

Robust workflows need resilient task execution. `auto-workflow` offers per-task retries with exponential backoff + jitter, timeouts, and flow-level failure policies.

## Task-Level Retries
```python
@task(retries=3, retry_backoff=1.0, retry_jitter=0.3)
async def unreliable():
    ...
```
Sequence (no jitter): 1.0s, 2.0s, 4.0s delays before final attempt.

## Timeout
```python
@task(timeout=5)
async def slow(): ...
```
If the inner coroutine does not finish in 5 seconds, a custom `TimeoutError` is raised (subject to retry logic if retries remain).

## Failure Policies (Flow Run)
Set at invocation:
```python
flow.run(failure_policy="fail_fast")       # default
flow.run(failure_policy="continue")        # downstream tasks attempt even if upstream failed
flow.run(failure_policy="aggregate")       # collect all failures, raise AggregateTaskError at end
```

## Error Surfaces
- `TaskExecutionError`: wrapper for a task failure.
- `RetryExhaustedError`: raised after final attempt fails (unless policy continues).
- `AggregateTaskError`: contains list of `TaskExecutionError` when using `aggregate` policy.

## Observability Hooks
Events emitted: `task_started`, `task_retry`, `task_failed`, `task_succeeded`.
Subscribe via:
```python
from auto_workflow import subscribe

def on_retry(evt):
    if evt.get("task") == "unreliable":
        print("retrying", evt)

subscribe("task_retry", on_retry)
```
