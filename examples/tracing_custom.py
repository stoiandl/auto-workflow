"""Example: Custom tracing integration.

Demonstrates:
- Replacing the default dummy tracer with a recording tracer
- Capturing flow and task span names & attributes
- Adding simple duration measurement

Run directly:
    python examples/tracing_custom.py
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

from auto_workflow import flow, task
from auto_workflow.tracing import set_tracer


# --- Custom tracer implementation ---
class RecordingTracer:
    """Minimal tracer that records span lifecycle with durations.

    Each entry appended to self.records as a tuple:
        (phase, name, attrs, duration_ms or None)
    phase: 'start' or 'end'.
    """
    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict[str, Any], float | None]] = []

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any):  # type: ignore[override]
        start = time.time()
        self.records.append(("start", name, attrs, None))
        try:
            yield {"name": name, **attrs}
        finally:
            dur = (time.time() - start) * 1000.0
            self.records.append(("end", name, attrs, dur))

# Install custom tracer
rec = RecordingTracer()
set_tracer(rec)

# --- Define tasks & flow ---
@task  # sync task defaults to thread executor
def extract() -> list[int]:
    time.sleep(0.01)
    return [1, 2, 3]

@task
async def transform(data: list[int]) -> list[int]:
    await asyncio.sleep(0.01)
    return [d * 10 for d in data]

@task
def load(items: list[int]) -> int:
    return sum(items)

@flow
def etl_flow():
    raw = extract()
    mapped = transform(raw)
    total = load(mapped)
    return total

# --- Run when executed as script ---
if __name__ == "__main__":
    result = etl_flow.run()
    print(f"Flow result: {result}")
    print("Captured spans (phase, name, attrs, duration_ms):")
    for phase, name, attrs, dur in rec.records:
        if phase == "end":
            print(f"  {phase:5} | {name:20} | attrs={attrs} | dur={dur:.2f}ms")
        else:
            print(f"  {phase:5} | {name:20} | attrs={attrs}")

    # Example: derive total time of task spans only
    task_durations = [
        dur
        for phase, name, _, dur in rec.records
        if phase == 'end' and name.startswith('task:')
    ]
    print(f"Total task time (ms): {sum(task_durations):.2f}")
