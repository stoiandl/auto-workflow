import threading
import time
from typing import List, Tuple

from auto_workflow import flow, task
from auto_workflow.exceptions import TaskExecutionError
from auto_workflow.secrets import StaticMappingSecrets, secret, set_secrets_provider
from auto_workflow.artifacts import get_store, ArtifactRef

MAIN_THREAD_ID = threading.get_ident()

# --- Off-main-thread execution ---
@task(run_in="thread")
def _capture_thread_id() -> int:
    return threading.get_ident()

@flow
def thread_id_flow():
    # Single thread task to verify it does not execute on main thread
    return _capture_thread_id()

# --- Parallel overlap measurement ---
_overlap_records: List[Tuple[float, float]] = []

@task(run_in="thread")
def _sleepy(idx: int, delay: float = 0.05) -> int:
    start = time.time()
    time.sleep(delay)
    end = time.time()
    _overlap_records.append((start, end))
    return idx

@flow
def parallel_thread_flow():
    a = _sleepy(1)
    b = _sleepy(2)
    return a, b

# --- Cache de-dup in thread mode ---
_thread_cache_counter = {"n": 0}

@task(run_in="thread", cache_ttl=60)
def _thread_cached(x: int) -> int:
    _thread_cache_counter["n"] += 1
    return x * 2

@flow
def thread_cache_flow():
    a = _thread_cached(5)
    b = _thread_cached(5)
    return a, b

# --- Exception propagation from thread task ---
@task(run_in="thread", retries=0)
def _thread_fail():
    # Explicit retries=0 (default) for clarity; non-timeout errors become
    # RetryExhaustedError wrapper at scheduler boundary.
    raise ValueError("boom-thread")

@flow
def thread_fail_flow():
    return _thread_fail()

# --- max_concurrency gating with thread tasks ---
_conc_state = {"current": 0, "max": 0}

@task(run_in="thread")
def _bounded_thread(x: int) -> int:
    _conc_state["current"] += 1
    _conc_state["max"] = max(_conc_state["max"], _conc_state["current"])
    try:
        time.sleep(0.03)
        return x
    finally:
        _conc_state["current"] -= 1

@flow
def bounded_thread_flow():
    return [_bounded_thread(i) for i in range(6)]

# --- Secret access in thread ---
@task(run_in="thread")
def _thread_secret() -> str:
    return secret("THREAD_KEY")

@flow
def thread_secret_flow():
    return _thread_secret()

# --- Artifact persistence in thread tasks ---
_persist_counter = {"n": 0}

@task(run_in="thread", persist=True, cache_ttl=60)
def _persist_thread_task():
    _persist_counter["n"] += 1
    return {"v": _persist_counter["n"]}

@flow
def persist_thread_flow():
    a = _persist_thread_task()
    b = _persist_thread_task()
    return a, b

# ===================== Tests ===================== #

def test_thread_exec_not_main():
    tid = thread_id_flow.run()
    assert isinstance(tid, int)
    # Ensure execution switched to a pool thread
    assert tid != MAIN_THREAD_ID


def test_thread_parallel_overlap():
    _overlap_records.clear()
    out = parallel_thread_flow.run()
    assert out == (1, 2)
    assert len(_overlap_records) == 2
    (s1, e1), (s2, e2) = _overlap_records
    # Intervals should overlap if executed in parallel
    assert (s1 < e2) and (s2 < e1)


def test_thread_cache_dedup():
    _thread_cache_counter["n"] = 0
    r = thread_cache_flow.run()
    assert r == (10, 10)
    # Only one underlying execution due to in-flight cache de-dup
    assert _thread_cache_counter["n"] == 1


def test_thread_exception_propagation():
    try:
        thread_fail_flow.run()
    except TaskExecutionError as e:
        from auto_workflow.exceptions import RetryExhaustedError

        # Expect RetryExhaustedError whose original is ValueError
        assert isinstance(e.original, RetryExhaustedError)
    else:  # pragma: no cover
        raise AssertionError("Expected TaskExecutionError wrapping RetryExhaustedError")


def test_thread_max_concurrency_enforced():
    _conc_state["current"] = 0
    _conc_state["max"] = 0
    out = bounded_thread_flow.run(max_concurrency=2)
    assert sorted(out) == list(range(6))
    assert _conc_state["max"] <= 2


def test_thread_secret_access():
    set_secrets_provider(StaticMappingSecrets({"THREAD_KEY": "val123"}))
    assert thread_secret_flow.run() == "val123"


def test_thread_persist_task_dedup_same_flow():
    _persist_counter["n"] = 0
    a_ref, b_ref = persist_thread_flow.run()
    assert isinstance(a_ref, ArtifactRef) and isinstance(b_ref, ArtifactRef)
    # dedup => only one execution
    assert _persist_counter["n"] == 1
    store = get_store()
    assert store.get(a_ref)["v"] == 1
    assert store.get(b_ref)["v"] == 1
