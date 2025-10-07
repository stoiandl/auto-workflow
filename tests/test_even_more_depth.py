import asyncio
import os
import random
import time

from auto_workflow import FailurePolicy, fan_out, flow, task
from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.config import reload_config
from auto_workflow.exceptions import AggregateTaskError, TaskExecutionError
from auto_workflow.metrics_provider import InMemoryMetrics, set_metrics_provider
from auto_workflow.middleware import clear, register
from auto_workflow.secrets import StaticMappingSecrets, secret, set_secrets_provider
from auto_workflow.tracing import set_tracer


# --- Stress dynamic fan-out (single-level) with variable batch sizes ---
@task
def _emit_range(n: int):
    return list(range(n))

@task
def _id(x): return x

@flow
def dynamic_stress_flow(n: int):
    r = _emit_range(n)
    mapped = fan_out(_id, r)
    return mapped

def test_dynamic_stress_various_sizes():
    for n in [0,1,2,5,10]:
        out = dynamic_stress_flow.run(n)
        assert out == list(range(n))

# --- Process executor + cache + persistence interplay ---
@task(run_in="process", cache_ttl=30, persist=True)
def _proc_heavy(x: int):
    return {"x": x, "v": x * x}

@flow
def proc_cache_flow():
    a = _proc_heavy(4)
    b = _proc_heavy(4)
    return a, b

def test_process_cache_persist_dedup():
    a, b = proc_cache_flow.run()
    assert isinstance(a, ArtifactRef) and isinstance(b, ArtifactRef)
    store = get_store()
    assert store.get(a)["v"] == 16
    # dedup ensures one execution -> underlying artifact value consistent
    assert store.get(b)["v"] == 16

# --- Mixed failure policies: aggregate collects multiple ---
@task
def _boom1(): raise RuntimeError("boom1")
@task
def _boom2(): raise RuntimeError("boom2")
@task
def _ok(): return 7

@flow
def aggregate_two_fail():
    a = _boom1()
    b = _boom2()
    c = _ok()
    return a, b, c

def test_aggregate_policy_collects():
    try:
        aggregate_two_fail.run(failure_policy=FailurePolicy.AGGREGATE)
        raise AssertionError("expected AggregateTaskError")
    except AggregateTaskError as e:
        rep = repr(e)
        assert "_boom1" in rep and "_boom2" in rep

# --- Secrets concurrency: ensure provider used at execution time ---
@task
async def _use_secret_async():
    await asyncio.sleep(0)
    return secret("TOKEN")

@flow
def secret_concurrent_flow():
    a = _use_secret_async()
    b = _use_secret_async()
    return a, b

def test_secret_concurrent_reads():
    set_secrets_provider(StaticMappingSecrets({"TOKEN": "alpha"}))
    out1 = secret_concurrent_flow.run()
    assert out1 == ("alpha", "alpha")
    set_secrets_provider(StaticMappingSecrets({"TOKEN": "beta"}))
    out2 = secret_concurrent_flow.run()
    assert out2 == ("beta", "beta")

# --- Priority stability: equal priority tasks should still all run.
# Order not enforced but ensure no duplication.
@task(priority=5)
def _prio_a(): return "A"
@task(priority=5)
def _prio_b(): return "B"
@task(priority=5)
def _prio_c(): return "C"

@flow
def prio_equal_flow():
    a = _prio_a()
    b = _prio_b()
    c = _prio_c()
    return [a, b, c]

def test_priority_equal_runs_all():
    out = prio_equal_flow.run()
    assert sorted(out) == ["A","B","C"]

# --- Middleware resilience: exception in middleware should not break others (caught internally) ---
async def bad_mw(next_call, task_def, args, kwargs):
    raise RuntimeError("mw fail")
async def pass_mw(next_call, task_def, args, kwargs):
    return await next_call()

@task
def _mw_task(): return 1

@flow
def mw_flow():
    return _mw_task()

def test_middleware_exception_resilience():
    clear()
    register(bad_mw)
    register(pass_mw)
    # Should still execute task despite mw failure (middleware_error emitted, chain continues)
    captured = []
    from auto_workflow.events import subscribe
    subscribe("middleware_error", lambda e: captured.append(e))
    out = mw_flow.run()
    assert out == 1
    assert captured and captured[0]["task"] == "_mw_task"

# --- Config env numeric coercion for max_dynamic_tasks already tested; extend
# with non-digit fallback ---

def test_env_override_non_digit(monkeypatch):  # type: ignore
    monkeypatch.setenv("AUTO_WORKFLOW_MAX_DYNAMIC_TASKS", "notanumber")
    cfg = reload_config()
    # library leaves string; Flow coercion will ignore non-digit
    assert cfg["max_dynamic_tasks"] == "notanumber"

# --- Tracing replacement mid-run (flow span should use latest tracer) ---
class RecordTracer:
    def __init__(self):
        self.names = []
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        self.names.append(name)
        yield {"name": name}

@task
async def _trace_example():
    await asyncio.sleep(0)
    return 3

@flow
def trace_replace_flow():
    return _trace_example()

def test_tracer_replacement():
    t = RecordTracer()
    set_tracer(t)
    assert trace_replace_flow.run() == 3
    assert any(n.startswith("task:_trace_example") for n in t.names)

# --- Ensure run_in inference negative: explicitly forcing async on sync
# function preserves value ---
@task(run_in="async")
def _forced_async_sync(): return 5

def test_forced_async_sync_execution():
    assert _forced_async_sync.run_in == "async"
    assert _forced_async_sync() == 5  # immediate execution path
