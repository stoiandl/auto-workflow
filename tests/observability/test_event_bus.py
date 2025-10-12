from auto_workflow.events import emit, subscribe


def test_event_bus_subscribe_and_emit(capsys):
    out = {}

    def cb(payload):
        out.update(payload)

    subscribe("hello", cb)
    emit("hello", {"a": 1})
    assert out == {"a": 1}
