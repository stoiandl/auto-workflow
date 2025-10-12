from auto_workflow import flow


@flow
def trivial():
    return {"hello": "world"}


def test_flow_trivial_return():
    out = trivial.run()
    assert out == {"hello": "world"}
