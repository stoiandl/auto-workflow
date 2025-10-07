# Middleware & Events

Middleware allows cross-cutting concerns (logging, metrics enrichment, tracing augmentation) without modifying task bodies.

## Register Middleware
```python
from auto_workflow.middleware import register

async def capture(next_call, task_def, args, kwargs):
    print("before", task_def.name)
    try:
        return await next_call()
    finally:
        print("after", task_def.name)

register(capture)
```
Middleware signature: `(next_call: Callable[[], Awaitable[Any]], task_def, args: tuple, kwargs: dict) -> Awaitable[Any]`.

## Ordering
Middleware run in registration order (outermost first). Each must call `await next_call()` to proceed.

## Events
Subscribe to lifecycle events:
```python
from auto_workflow import subscribe

def on_success(evt):
    print("task succeeded", evt)

subscribe("task_succeeded", on_success)
```

Event payloads are dicts; avoid raising in handlers (exceptions are swallowed to protect core execution).
