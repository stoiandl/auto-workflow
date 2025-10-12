# Quickstart

This guide gets you from zero to a running flow in a couple of minutes.

## Installation

### From PyPI
```bash
pip install auto-workflow
```

### Local Development Setup
```bash
# Clone repository
git clone https://github.com/stoiandl/auto-workflow.git
cd auto-workflow
# Install dependencies and dev tools with Poetry
poetry install --with dev
poetry run pytest -q  # sanity check
```

## Define Tasks & Flow
```python
from auto_workflow import task, flow, fan_out

@task
def numbers() -> list[int]:
    return [1, 2, 3, 4]

@task
def square(x: int) -> int:
    return x * x

@task
def total(values: list[int]) -> int:
    return sum(values)

@flow
def pipeline():
    nums = numbers()
    squares = fan_out(square, nums)  # dynamic fan-out: create tasks for each number
    return total(squares)

if __name__ == "__main__":
    result = pipeline.run()
    print("Result:", result)
```

## Run & Inspect
```bash
python pipeline.py
```

Describe the graph without executing:
```python
print(pipeline.describe())
```

Export a DOT graph:
```python
dot = pipeline.export_dot()
with open("pipeline.dot", "w") as f:
    f.write(dot)
```
Render with Graphviz:
```bash
dot -Tpng pipeline.dot -o pipeline.png
```

## Add a Retry & Timeout
```python
@task(retries=3, retry_backoff=1.0, retry_jitter=0.2, timeout=10)
def flaky():
    ...
```

## Enable Caching
```python
@task(cache_ttl=3600)
def expensive(x: int) -> int:
    return compute(x)
```

## Persist Large Results
```python
@task(persist=True)
def produce_large():
    return {"big": list(range(1000000))}
```
The task returns an `ArtifactRef` when persisted.

## Dynamic Fan-Out (Runtime)
See [Dynamic Fan-Out](dynamic-fanout.md) for mapping tasks created after upstream completion.

## Next Steps
- Learn the [Task API](concepts/tasks.md)
- Handle [Retries & Failures](retries-timeouts-failure.md)
- Explore [Observability](observability.md)
