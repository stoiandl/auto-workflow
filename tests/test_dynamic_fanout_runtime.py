from auto_workflow import fan_out, flow, task


@task
def produce():
    return [1, 2, 3, 4]


@task
def square(x: int) -> int:
    return x * x


@task
def aggregate(xs: list[int]) -> int:
    return sum(xs)


@flow
def dynamic_flow():
    items = produce()
    squares = fan_out(square, items)  # runtime expansion
    total = aggregate(squares)
    return total


def test_dynamic_fanout():
    assert dynamic_flow.run() == 30
