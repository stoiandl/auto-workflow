# Flows

A Flow defines how tasks compose into a DAG. Use the `@flow` decorator on a function whose body instantiates tasks and passes results to other tasks.

## Basic Flow
```python
from auto_workflow import task, flow

@task
def inc(x: int) -> int: return x + 1

@task
def add(a: int, b: int) -> int: return a + b

@flow
def two_step():
    x = inc(1)
    y = inc(x)
    return add(x, y)

print(two_step.run())
```

## Description Without Execution
```python
print(two_step.describe())
# => {"flow": "two_step", "nodes": [...], "count": N}
```

## Exporting Graph
```python
print(two_step.export_dot())      # DOT format
print(two_step.export_graph())    # adjacency JSON
```

When using dynamic fan-out (`fan_out(...)`), DOT export renders barrier nodes (`fanout:n`) as
diamonds and wires dependencies through them. This removes any direct shortcut edges from the
original source to downstream consumers, ensuring the visual ordering matches execution.

## Parameters
Pass runtime parameters:
```python
@flow
def configured():
    from auto_workflow.context import get_context
    ctx = get_context()
    n = ctx.params.get("n", 5)
    # build tasks using n
    ...

configured.run(params={"n": 10})
```

## Failure Policies
Configure at run time:
```python
two_step.run(failure_policy="continue")
```
Options: `fail_fast` (default), `continue`, `aggregate`.

## Concurrency Limit
Limit simultaneous in-flight tasks:
```python
two_step.run(max_concurrency=4)
```

## Cancellation
A cancellation event is internally supported; external cooperative cancellation can be added by wrapping the scheduler (see [Priority & Cancellation](priority-cancellation.md)).
