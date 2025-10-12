from auto_workflow import flow, task


@task
def a():
    return 1


@task
def b(x: int):
    return x + 1


@flow
def f():
    x = a()
    y = b(x)
    return y


def test_flow_export_dot_and_graph():
    dot = f.export_dot()
    assert '"a:1" -> "b:1";' in dot
    graph = f.export_graph()
    assert any(n == "a:1" for n in graph)
    assert any(n == "b:1" for n in graph)
