from auto_workflow import flow, task


@task
def a():
    return 1


@task
def b(x: int):
    return x + 1


@flow
def sample():
    x = a()
    y = b(x)
    return y


def test_flow_describe():
    desc = sample.describe()
    assert desc["flow"] == "sample"
    assert desc["count"] == 2
    tasks = {n["task"] for n in desc["nodes"]}
    assert tasks == {"a", "b"}
    # ensure dependency recorded
    node_b = next(n for n in desc["nodes"] if n["task"] == "b")
    assert len(node_b["upstream"]) == 1
