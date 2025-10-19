"""Integration tests for ADLS2 connector with the flow/task API (mocked).

These tests mock the Azure SDK surface so they run hermetically without network
or environment credentials. They exercise:
- tasks/flows/fan_out orchestration
- basic upload/download/list/delete
- connection string vs account_url branches in open()
- logging middleware + events (smoke)
- tracing spans (smoke)
- caching and in-flight deduplication (indirectly via registry/client reuse)
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

import pytest

from auto_workflow import fan_out, flow, task
from auto_workflow.connectors import adls2, registry as _registry
from auto_workflow.metrics_provider import (
    InMemoryMetrics,
    get_metrics_provider,
    set_metrics_provider,
)
from auto_workflow.tracing import get_tracer, set_tracer
from tests.connectors.adls2_fakes import inject as _inject_fakes


def _unique_path(base: str) -> str:
    return f"{base}_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def profile() -> str:
    return "example"


@pytest.fixture()
def fs(monkeypatch, profile: str):
    _inject_fakes(monkeypatch)
    with adls2.client(profile) as c:
        yield c


def test_basic_upload_download_delete(fs):
    cont = "aw-it"
    path = _unique_path("test/basic.txt")
    etag = fs.upload_bytes(cont, path, b"hello-world", content_type="text/plain")
    assert etag is not None and isinstance(etag, str)
    data = fs.download_bytes(cont, path)
    assert data == b"hello-world"
    paths = list(fs.list_paths(cont, prefix=path.rsplit("/", 1)[0]))
    assert any("basic.txt" in p["path"] for p in paths)
    fs.delete_path(cont, path)
    assert fs.exists(cont, path) is False


def test_flow_with_tasks_and_fanout(monkeypatch, profile: str):
    _inject_fakes(monkeypatch)
    cont = "aw-it"
    base = _unique_path("flow/fanout")

    @task
    def put_one(idx: int) -> str:
        p = f"{base}/file_{idx}.txt"
        with adls2.client(profile) as c:
            c.upload_bytes(cont, p, f"val-{idx}".encode(), content_type="text/plain")
        return p

    @task
    def read_sum(paths: Iterable[str]) -> int:
        total = 0
        with adls2.client(profile) as c:
            for p in paths:
                total += len(c.download_bytes(cont, p))
        return total

    @task
    def cleanup(paths: Iterable[str], _dep: int) -> int:
        n = 0
        with adls2.client(profile) as c:
            for p in paths:
                c.delete_path(cont, p)
                n += 1
        return n

    @flow
    def f() -> tuple[int, int]:
        outs = fan_out(put_one, list(range(5)))
        total = read_sum(outs)
        removed = cleanup(outs, total)
        return total, removed

    total, removed = f.run()
    assert total > 0 and removed == 5


def test_connection_string_branch(monkeypatch, profile: str):
    _inject_fakes(
        monkeypatch,
        with_conn_str=True,
        retries=3,
        timeouts={"connect_s": 0.1, "operation_s": 0.2},
    )
    cont = "aw-it"
    p = _unique_path("connstr/one.txt")
    with adls2.client(profile) as c:
        etag = c.upload_bytes(cont, p, b"x")
        assert etag
        assert c.exists(cont, p)
        c.delete_path(cont, p)
        assert not c.exists(cont, p)


def test_metrics_and_tracing_smoke(monkeypatch, profile: str):
    _inject_fakes(monkeypatch)
    prev_metrics = get_metrics_provider()
    set_metrics_provider(InMemoryMetrics())
    prev_tracer = get_tracer()
    set_tracer(None)
    try:
        cont = "aw-it"
        p = _unique_path("obs/trace.txt")
        with adls2.client(profile) as c:
            c.upload_bytes(cont, p, b"x")
            list(c.download_stream(cont, p))
            c.delete_path(cont, p)
    finally:
        set_metrics_provider(prev_metrics)
        set_tracer(prev_tracer)


def test_make_dirs_noop(monkeypatch, profile: str):
    _inject_fakes(monkeypatch)
    cont = "aw-it"
    d = _unique_path("dir/path")
    with adls2.client(profile) as c:
        # Should not raise
        c.make_dirs(cont, d, exist_ok=True)
