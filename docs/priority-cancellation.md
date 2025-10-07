# Priority Scheduling & Cancellation

## Priority
Each task has an integer `priority` (default 0). Higher numbers schedule earlier among ready tasks.
```python
@task(priority=10)
def high(): ...

@task(priority=1)
def low(): ...
```

If both become runnable simultaneously, `high` executes first.

## Cancellation
Flows respect a cancellation event internally. External cooperative cancellation pattern:
```python
import asyncio
from auto_workflow import flow, task
from auto_workflow.scheduler import execute_dag

# (Advanced) Wrap scheduler with custom cancel event if integrating into a long-running service.
```
Currently, user-triggered cancellation can be added by modifying the scheduler invocation—future public API helper may be provided.

## Backpressure & Concurrency
Limit active tasks with `max_concurrency` at flow run time:
```python
flow.run(max_concurrency=8)
```
This bounds simultaneous task executions (including dynamically expanded tasks).
