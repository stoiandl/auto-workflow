import asyncio
import time

import pytest

from auto_workflow import FailurePolicy, flow, task
from auto_workflow.exceptions import TaskExecutionError


@task
def slow_ok():
    # noticeable delay
    time.sleep(0.2)
    return 1


@task
def boom():
    raise RuntimeError("boom")


@flow
def mixed_flow():
    # fan-out is not necessary; two independent tasks ensure one fails and one is pending
    a = slow_ok()
    b = boom()
    return a, b


def test_fail_fast_cancels_pending():
    with pytest.raises(TaskExecutionError):
        mixed_flow.run(failure_policy=FailurePolicy.FAIL_FAST)
