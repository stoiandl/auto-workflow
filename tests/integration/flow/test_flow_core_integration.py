"""Core flow/task integration tests that do not require external services.

These cover logging, events, tracing, caching, and priority ordering behaviors
using simple tasks and flows without any Postgres dependency.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import pytest

from auto_workflow import fan_out, flow, subscribe, task
from auto_workflow.metrics_provider import (
    InMemoryMetrics,
    get_metrics_provider,
    set_metrics_provider,
)
from auto_workflow.tracing import get_tracer, set_tracer


class _ListHandler:
    def __init__(self) -> None:
        import logging

        self.records: list[str] = []
        self._handler = logging.Handler()

        def emit(record):  # type: ignore[no-untyped-def]
            self.records.append(record.getMessage())

        self._handler.emit = emit  # type: ignore[method-assign]
        self._logger = logging.getLogger("auto_workflow.tasks")
        # Replace handlers for a clean capture
        self._prev_handlers = self._logger.handlers[:]
        self._logger.handlers = [self._handler]
        self._logger.propagate = False

    def close(self) -> None:
        self._logger.handlers = self._prev_handlers


@pytest.fixture()
def capture_logs():
    h = _ListHandler()
    try:
        yield h
    finally:
        h.close()


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any):  # pragma: no cover - simple impl
        info = {"name": name, **attrs}
        self.spans.append(info)
        try:
            yield info
        finally:
            pass


@pytest.fixture()
def tracer_patch():
    prev = get_tracer()
    t = _Tracer()
    set_tracer(t)
    try:
        yield t
    finally:
        set_tracer(prev)


@pytest.fixture()
def metrics_patch():
    prev = get_metrics_provider()
    m = InMemoryMetrics()
    set_metrics_provider(m)
    try:
        yield m
    finally:
        set_metrics_provider(prev)


def test_flow_logs_structured(capture_logs):
    @task
    def noop():
        return 1

    @flow
    def f():
        return noop()

    assert f.run() == 1
    joined = "\n".join(capture_logs.records)
    assert "flow_started" in joined and "flow_completed" in joined
    assert "task_ok" in joined or "task_err" in joined


def test_events_bus_flow_completed_payload():
    payloads: list[dict[str, Any]] = []
    subscribe("flow_completed", lambda p: payloads.append(p))

    @task
    def noop():
        return 1

    @flow
    def f():
        return [noop(), noop()]

    res = f.run()
    assert res == [1, 1]
    assert payloads and "tasks" in payloads[-1] and payloads[-1]["tasks"] >= 1


def test_tracing_spans_emitted(tracer_patch):
    @task
    def noop():
        return 2

    @flow
    def f():
        return [noop(), noop()]

    assert f.run() == [2, 2]
    names = [s.get("name") for s in tracer_patch.spans]
    assert any(n and n.startswith("task:") for n in names)


def test_caching_task_dedup_within_run(metrics_patch):
    calls = {"n": 0}

    @task(cache_ttl=5)
    def slow(x: int) -> int:
        calls["n"] += 1
        time.sleep(0.2)
        return x * 2

    @flow
    def f():
        return fan_out(slow, [3, 3])

    assert f.run(max_concurrency=2) == [6, 6]
    assert calls["n"] == 1
    assert metrics_patch.counters.get("dedup_joins", 0.0) >= 1.0


def test_result_cache_hit_between_runs(metrics_patch):
    calls = {"n": 0}

    @task(cache_ttl=5)
    def slow(x: int) -> int:
        calls["n"] += 1
        time.sleep(0.1)
        return x

    @flow
    def f():
        return slow(7)

    assert f.run() == 7
    assert f.run() == 7
    assert calls["n"] == 1
    assert metrics_patch.counters.get("cache_sets", 0.0) >= 1.0


def test_middleware_logging_applied(capture_logs):
    @task
    def work() -> int:
        return 123

    @flow
    def f():
        return [work(), work()]

    assert f.run() == [123, 123]
    msg = "\n".join(capture_logs.records)
    assert "task_ok" in msg


def test_priority_order_affects_start_events():
    seen: list[str] = []
    subscribe("task_started", lambda p: seen.append(p.get("task", "")))

    @task(name="low", priority=0)
    def low():
        return 0

    @task(name="high", priority=10)
    def high():
        return 1

    @flow
    def f():
        return [low(), high()]

    assert f.run(max_concurrency=2) == [0, 1]
    assert seen and seen[0] == "high"
