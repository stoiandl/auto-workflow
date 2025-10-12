from auto_workflow import task
from auto_workflow.fanout import fan_out


def test_fanout_immediate_execution_outside_flow():
    @task
    def double(x: int) -> int:
        return x * 2

    out = fan_out(double, [1, 2, 3])
    assert out == [2, 4, 6]
