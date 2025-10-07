"""Example: Simple ETL style data pipeline flow.

Demonstrates:
- Extract (mock API call)
- Transform (clean & aggregate)
- Load (persist artifact)
- Retry + timeout + caching
"""
from __future__ import annotations
import random
import time
from typing import Any

from auto_workflow import task, flow
from auto_workflow.artifacts import get_store

# --- Tasks ---

@task(timeout=2.0, retries=1, retry_backoff=0.2)
def extract_raw(batch_id: int) -> list[dict[str, Any]]:
    # Simulate variable latency
    time.sleep(0.05)
    if random.random() < 0.05:
        raise RuntimeError("Transient upstream failure")
    return [
        {"user": "u1", "value": 10 + batch_id},
        {"user": "u2", "value": 14 + batch_id},
        {"user": "u3", "value": None},  # dirty row
    ]

@task
def clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["value"] is not None]

@task
def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(r["value"] for r in rows)  # type: ignore
    return {"count": len(rows), "total": total, "avg": total / len(rows)}

@task(persist=True)
def persist_metrics(metrics: dict[str, Any]):
    # The persist flag will store the result in artifact store automatically
    return metrics

# --- Flow ---
@flow
def etl_flow(batch_id: int = 1):
    raw = extract_raw(batch_id)
    cleaned = clean_rows(raw)
    metrics = aggregate(cleaned)
    ref = persist_metrics(metrics)
    return ref

if __name__ == "__main__":
    ref = etl_flow.run()
    store = get_store()
    print("Stored metrics artifact:", store.get(ref))
