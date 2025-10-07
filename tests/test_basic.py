from auto_workflow import task, flow, fan_out, FailurePolicy

@task
def add(a: int, b: int) -> int:
    return a + b

@task
async def mul_async(a: int, b: int) -> int:
    return a * b

@flow
def simple_flow():
    s1 = add(1, 2)
    s2 = mul_async(3, 4)
    return s1, s2

def test_simple_flow():
    result = simple_flow.run()
    assert result == (3, 12)


@task
def square(x: int) -> int:
    return x * x

@task
def aggregate(xs: list[int]) -> int:
    return sum(xs)

@flow
def fan_out_flow():
    nums = [1, 2, 3, 4]
    squares = fan_out(square, nums)
    total = aggregate(squares)  # list of task invocations becomes dependency list
    return total


def test_fan_out_flow():
    assert fan_out_flow.run() == 30


# Retry & failure policy tests
counter = {"n": 0}

@task(retries=2, retry_backoff=0.0)
def flaky() -> int:
    counter["n"] += 1
    if counter["n"] < 3:
        raise ValueError("boom")
    return counter["n"]

@flow
def retry_flow():
    return flaky()


def test_retry_flow():
    counter["n"] = 0
    assert retry_flow.run() == 3


@task
def fail_task():
    raise RuntimeError("fail")

@task
def ok_task() -> int:
    return 42

@flow
def continue_flow():
    a = fail_task()
    b = ok_task()
    return a, b


def test_failure_policy_continue():
    res = continue_flow.run(failure_policy=FailurePolicy.CONTINUE)
    # first element is a TaskExecutionError, second is 42
    from auto_workflow.exceptions import TaskExecutionError
    assert isinstance(res[0], TaskExecutionError)
    assert res[1] == 42


@flow
def aggregate_flow():
    a = fail_task()
    b = fail_task()
    return [a, b]

def test_failure_policy_aggregate():
    from auto_workflow.exceptions import AggregateTaskError
    try:
        aggregate_flow.run(failure_policy=FailurePolicy.AGGREGATE)
    except AggregateTaskError as e:
        assert len(e.errors) >= 2
    else:  # pragma: no cover
        raise AssertionError("Expected AggregateTaskError")


@task(cache_ttl=60)
def cached_value(x: int) -> int:
    return x * 2

@flow
def cache_flow(x: int):
    a = cached_value(x)
    b = cached_value(x)  # should reuse cached result
    return a, b

def test_cache_reuse():
    r1 = cache_flow.run(5)
    assert r1 == (10, 10)


@task(timeout=0.01, retries=0, run_in="thread")
def slow_task():
    import time as _t
    _t.sleep(0.05)
    return 1

@flow
def timeout_flow():
    return slow_task()


def test_timeout():
    from auto_workflow.exceptions import RetryExhaustedError, TimeoutError, TaskExecutionError
    try:
        timeout_flow.run()
    except RetryExhaustedError as e:  # underlying TimeoutError wrapped when retries exhausted
        assert isinstance(e.original, TimeoutError)
    except TaskExecutionError as e:
        # timeout wrapped by scheduler fail_fast policy
        assert "TimeoutError" in repr(e)
    except TimeoutError:  # direct path (no retry wrapper)
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected timeout error")


@task(persist=True)
def large_result() -> list[int]:
    return list(range(100))

@flow
def persist_flow():
    return large_result()


def test_persist_artifact():
    from auto_workflow.artifacts import ArtifactRef, get_store
    ref = persist_flow.run()
    assert isinstance(ref, ArtifactRef)
    store = get_store()
    value = store.get(ref)
    assert value[0] == 0 and value[-1] == 99 and len(value) == 100
