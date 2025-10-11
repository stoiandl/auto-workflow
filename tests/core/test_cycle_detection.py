from auto_workflow import flow, task
from auto_workflow.build import _inject_cycle
from auto_workflow.exceptions import CycleDetectedError


@task
def t1():
    return 1


@task
def t2(x: int):
    return x + 1


@flow
def cyc():
    a = t1()
    b = t2(a)
    # inject cycle artificially a <-> b
    _inject_cycle(a, b)
    return b


def test_cycle_detection():
    try:
        cyc.run()
    except CycleDetectedError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected cycle detection error")
