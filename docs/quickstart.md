# Quickstart

This guide gets you from zero to a running flow in a couple of minutes.

## Installation (Local Source Checkout)
```bash
# Clone repository
git clone https://github.com/andreistoica/auto-workflow.git
cd auto-workflow
# Create virtual environment (Python >= 3.12)
python -m venv .venv
source .venv/bin/activate
pip install -e .
# (Optional) install dev tools
pip install pytest pytest-asyncio ruff
```

## Define Tasks & Flow
```python
from auto_workflow import task, flow

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
    squares = [square(n) for n in nums]  # static fan-out (list comprehension of task calls)
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
