from auto_workflow import FailurePolicy, flow, task
from auto_workflow.exceptions import AggregateTaskError, TaskExecutionError


@task
def good():
    return 1


@task
def bad():
    raise ValueError("boom")


@task
def uses(x):
    return x


@flow
def fail_fast_flow():
    a = bad()
    b = uses(a)
    return b


@flow
def continue_flow():
    a = bad()
    b = good()
    return [a, b]


@flow
def aggregate_flow():
    a = bad()
    b = bad()
    return [a, b]


def test_fail_fast_policy():
    try:
        fail_fast_flow.run(failure_policy=FailurePolicy.FAIL_FAST)
    except TaskExecutionError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected TaskExecutionError")


def test_continue_policy():
    res = continue_flow.run(failure_policy=FailurePolicy.CONTINUE)
    # First element should be TaskExecutionError placeholder
    assert hasattr(res[0], "task_name") or "Task" in res[0].__class__.__name__
    assert res[1] == 1


def test_aggregate_policy():
    try:
        aggregate_flow.run(failure_policy=FailurePolicy.AGGREGATE)
    except AggregateTaskError as e:
        assert len(e.errors) == 2
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected AggregateTaskError")
