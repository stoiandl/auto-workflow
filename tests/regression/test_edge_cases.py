import asyncio
import re
import time

from auto_workflow import FailurePolicy, fan_out, flow, task
from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.exceptions import (
    AggregateTaskError,
    RetryExhaustedError,
    TaskExecutionError,
    TimeoutError,
)

# ---------- CACHING & TTL ----------
_counter_cache = {"n": 0}


@task(cache_ttl=1)
def cached_inc(x: int) -> int:
    _counter_cache["n"] += 1
    return x + 1


@flow
def cache_flow_ttl(x: int):
    a = cached_inc(x)
    b = cached_inc(x)
    return a, b


def test_cache_same_flow_reuse():
    _counter_cache["n"] = 0
    out = cache_flow_ttl.run(10)
    assert out == (11, 11)
    # Only one underlying execution
    assert _counter_cache["n"] == 1


def test_cache_new_flow_reexec_after_ttl_expiry():
    _counter_cache["n"] = 0
    cache_flow_ttl.run(5)
    assert _counter_cache["n"] == 1
    time.sleep(1.05)  # expire TTL
    cache_flow_ttl.run(5)
    assert _counter_cache["n"] == 2


# ---------- RETRIES ----------
_retry_state = {"attempts": 0}


@task(retries=3, retry_backoff=0.0)
def succeed_after_two():
    _retry_state["attempts"] += 1
    if _retry_state["attempts"] < 3:
        raise ValueError("not yet")
    return _retry_state["attempts"]


@task(retries=1, retry_backoff=0.0)
def always_fail():
    raise RuntimeError("boom")


@flow
def retry_success_flow():
    return succeed_after_two()


@flow
def retry_fail_flow():
    return always_fail()


def test_retry_eventual_success():
    _retry_state["attempts"] = 0
    assert retry_success_flow.run() == 3


def test_retry_exhausted_failure():
    try:
        retry_fail_flow.run()
    except TaskExecutionError as e:
        assert "boom" in str(e.original)
    else:  # pragma: no cover
        raise AssertionError("Expected failure")


# ---------- FAILURE POLICIES & DOWNSTREAM BEHAVIOR ----------
@task
def produce_a():
    return "A"


@task
def fail_mid():
    raise ValueError("mid")


@task
def concat(x, y):
    return f"{x}-{y}"


@flow
def downstream_continue():
    a = produce_a()
    b = fail_mid()
    c = concat(a, b)  # Will receive TaskExecutionError under CONTINUE
    return c


def test_failure_policy_continue_downstream_executes():
    res = downstream_continue.run(failure_policy=FailurePolicy.CONTINUE)
    assert isinstance(res, str)  # concat executed, stringified TaskExecutionError present
    assert res.startswith("A-")


@flow
def downstream_fail_fast():
    a = produce_a()
    b = fail_mid()
    c = concat(a, b)
    return c


def test_failure_policy_fail_fast_skips_downstream():
    try:
        downstream_fail_fast.run(failure_policy=FailurePolicy.FAIL_FAST)
    except TaskExecutionError:
        # concat never runs so exception originates from fail_mid
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected fail_fast propagation")


# ---------- AGGREGATE SUMMARY ( >5 failures truncation ) ----------
@task
def fail_generic():
    raise RuntimeError("x")


@flow
def many_fail_flow():
    fails = [fail_generic() for _ in range(7)]  # 7 failing tasks
    return fails


def test_aggregate_failure_summary():
    try:
        many_fail_flow.run(failure_policy=FailurePolicy.AGGREGATE)
    except AggregateTaskError as e:
        assert len(e.errors) == 7
        msg = str(e)
        # Contains +2 more due to truncation after 5
        assert "+2 more" in msg
    else:  # pragma: no cover
        raise AssertionError("Expected AggregateTaskError")


# ---------- FAN OUT EDGE CASES ----------
@task
def identity(x):
    return x


@flow
def empty_fan_out_flow():
    items = []
    mapped = fan_out(identity, items)
    return mapped  # expect empty list


def test_empty_fan_out():
    assert empty_fan_out_flow.run() == []


# ---------- NESTED STRUCTURE DEPENDENCIES ----------
@task
def double(x: int) -> int:
    return x * 2


@flow
def nested_structure_flow():
    a = double(2)
    b = double(3)
    structure = {"vals": [a, {"inner": (b, {"seq": [a, b]})}]}
    return structure


def test_nested_structure_resolution():
    res = nested_structure_flow.run()
    assert res["vals"][0] == 4
    assert res["vals"][1]["inner"][0] == 6


# ---------- PERSIST + CACHE COMBINATION ----------
@task(persist=True, cache_ttl=60)
def persist_cached() -> list[int]:
    return list(range(5))


@flow
def persist_cache_flow():
    a = persist_cached()
    b = persist_cached()
    return a, b


def test_persist_and_cache_reuse_ref():
    r1, r2 = persist_cache_flow.run()
    assert isinstance(r1, ArtifactRef) and isinstance(r2, ArtifactRef)
    # Should be same reference object due to cache reuse within flow
    assert r1 is r2
    store = get_store()
    assert store.get(r1) == [0, 1, 2, 3, 4]


# ---------- PROCESS EXECUTION ----------
@task(run_in="process")
def proc_add(a: int, b: int) -> int:
    return a + b


@flow
def process_flow():
    return proc_add(2, 3)


def test_process_executor():
    assert process_flow.run() == 5


# ---------- THREAD EXECUTION ----------
@task(run_in="thread")
def thread_mul(a: int, b: int) -> int:
    return a * b


@flow
def thread_flow():
    return thread_mul(4, 5)


def test_thread_executor():
    assert thread_flow.run() == 20


# ---------- FLOW WITH NO TASKS ----------
@flow
def trivial_flow():
    return {"plain": 123}


def test_trivial_flow_returns_structure():
    assert trivial_flow.run() == {"plain": 123}


# ---------- DIRECT TASK INVOCATION OUTSIDE FLOW ----------
@task
def direct_add(a: int, b: int) -> int:
    return a + b


def test_direct_task_invocation():
    # Direct call executes immediately outside flow
    assert direct_add(1, 2) == 3


# ---------- TIMEOUT WITH RETRIES (ensure wrapper) ----------
_timeout_state = {"n": 0}


@task(timeout=0.01, retries=1, retry_backoff=0.0, run_in="thread")
def flaky_timeout():
    _timeout_state["n"] += 1
    time.sleep(0.05)
    return 1


@flow
def flaky_timeout_flow():
    return flaky_timeout()


def test_timeout_with_retry_exhausted():
    try:
        flaky_timeout_flow.run()
    except TaskExecutionError as e:
        # Expect RetryExhaustedError containing TimeoutError or direct TimeoutError if logic changes
        if isinstance(e.original, RetryExhaustedError):
            assert isinstance(e.original.original, TimeoutError)
        else:
            assert isinstance(e.original, TimeoutError)
    else:  # pragma: no cover
        raise AssertionError("Expected timeout wrapped error")


# ---------- CONCURRENCY LIMIT ----------
_concurrency_obs = {"current": 0, "max": 0}


@task
async def slow_async(x: int) -> int:
    _concurrency_obs["current"] += 1
    _concurrency_obs["max"] = max(_concurrency_obs["max"], _concurrency_obs["current"])
    await asyncio.sleep(0.02)
    _concurrency_obs["current"] -= 1
    return x


@flow
def concurrency_flow():
    vals = [slow_async(i) for i in range(6)]
    return vals


def test_max_concurrency_enforced():
    _concurrency_obs["current"] = 0
    _concurrency_obs["max"] = 0
    out = concurrency_flow.run(max_concurrency=2)
    assert sorted(out) == list(range(6))
    assert _concurrency_obs["max"] <= 2
