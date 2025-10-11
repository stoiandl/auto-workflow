import asyncio
import inspect
import os
import time

from auto_workflow import FailurePolicy, fan_out, flow, task
from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.config import reload_config
from auto_workflow.events import subscribe
from auto_workflow.exceptions import AggregateTaskError
from auto_workflow.secrets import StaticMappingSecrets, secret, set_secrets_provider
from auto_workflow.tracing import get_tracer, set_tracer

# --- Auto executor inference tests ---


@task  # sync function, should default to thread
def _sync_inc(x: int) -> int:
    return x + 1


@task  # async coroutine, should default to async
async def _async_inc(x: int) -> int:
    await asyncio.sleep(0)
    return x + 1


@task(run_in="process")
def _proc_mul(x: int) -> int:
    return x * 2


def test_auto_executor_inference_defaults():
    assert _sync_inc.run_in == "thread"  # inferred
    assert _async_inc.run_in == "async"  # inferred from coroutine
    assert _proc_mul.run_in == "process"  # explicit override honored


# --- In-flight cache deduplication ---
_counter = {"n": 0}


@task(cache_ttl=60)
def _counted() -> int:
    _counter["n"] += 1
    # small delay to widen race window
    return _counter["n"]


@flow
def cache_dedup_flow():
    a = _counted()
    b = _counted()
    # return both raw results
    return a, b


def test_inflight_cache_dedup():
    _counter["n"] = 0
    out = cache_dedup_flow.run()
    # both results should be identical and only executed once
    assert out == (1, 1)
    assert _counter["n"] == 1


# --- Concurrency limit observation ---
_concurrency_state = {"current": 0, "max": 0}


@task
async def _bounded_work(delay: float = 0.02):
    _concurrency_state["current"] += 1
    _concurrency_state["max"] = max(_concurrency_state["max"], _concurrency_state["current"])
    try:
        await asyncio.sleep(delay)
    finally:
        _concurrency_state["current"] -= 1
    return 1


@flow
def concurrency_flow(n: int = 8):
    return [_bounded_work() for _ in range(n)]


def test_max_concurrency_enforced():
    _concurrency_state["current"] = 0
    _concurrency_state["max"] = 0
    concurrency_flow.run(max_concurrency=3)
    assert _concurrency_state["max"] <= 3


# --- Secrets provider integration ---


@task
def _use_secret():
    return secret("API_KEY")


@flow
def secret_flow():
    return _use_secret()


def test_static_mapping_secrets():
    set_secrets_provider(StaticMappingSecrets({"API_KEY": "abc123"}))
    assert secret_flow.run() == "abc123"


# --- Config environment override ---


def test_env_override_max_dynamic_tasks(monkeypatch):  # type: ignore
    monkeypatch.setenv("AUTO_WORKFLOW_MAX_DYNAMIC_TASKS", "9999")
    cfg = reload_config()
    assert cfg["max_dynamic_tasks"] == "9999"  # env keeps string form as implemented


# --- Tracing spans capture ---
class RecordingTracer:
    def __init__(self):
        self.spans = []

    class _SpanCtx:
        def __init__(self, outer, name, attrs):
            self.outer = outer
            self.name = name
            self.attrs = attrs

        async def __aenter__(self):
            self.start = time.time()
            return {"name": self.name, **self.attrs}

        async def __aexit__(self, exc_type, exc, tb):
            self.outer.spans.append((self.name, self.attrs))

    def span(self, name: str, **attrs):  # async context manager interface
        return self._SpanCtx(self, name, attrs)


@task
async def _trace_task(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


@flow
def tracing_flow():
    a = _trace_task(2)
    b = _trace_task(3)
    return a, b


def test_tracing_spans_collected():
    tracer = RecordingTracer()
    set_tracer(tracer)  # swap global tracer
    out = tracing_flow.run()
    assert out == (4, 6)
    names = [n for n, _ in tracer.spans]
    # Expect at least 2 task spans + 1 flow span
    assert any(n.startswith("flow:") for n in names)
    assert sum(1 for n in names if n.startswith("task:")) >= 2


# --- Aggregate failure policy ---
class SomeError(RuntimeError):
    pass


@task
def _fail_one():
    raise SomeError("boom1")


@task
def _fail_two():
    raise SomeError("boom2")


@task
def _ok():
    return 42


@flow
def aggregate_fail_flow():
    a = _fail_one()
    b = _fail_two()
    c = _ok()
    return a, b, c


def test_aggregate_failure_policy():
    # When using aggregate, we expect an AggregateTaskError capturing both failures
    try:
        aggregate_fail_flow.run(failure_policy=FailurePolicy.AGGREGATE)
        raise AssertionError("Should have raised AggregateTaskError")
    except AggregateTaskError as e:
        msgs = repr(e)
        assert "_fail_one" in msgs and "_fail_two" in msgs


# --- Persist + cache cross-flow TTL reuse ---
_persist_counter = {"k": 0}


@task(persist=True, cache_ttl=60)
def _persisted_counter():
    _persist_counter["k"] += 1
    return {"v": _persist_counter["k"]}


@flow
def persist_flow():
    a = _persisted_counter()
    b = _persisted_counter()
    return a, b


def test_persist_cache_same_flow_single_artifact():
    _persist_counter["k"] = 0
    a_ref, b_ref = persist_flow.run()
    assert isinstance(a_ref, ArtifactRef) and isinstance(b_ref, ArtifactRef)
    # dedup ensures single execution
    assert _persist_counter["k"] == 1
    store = get_store()
    assert store.get(a_ref)["v"] == 1
    assert store.get(b_ref)["v"] == 1
