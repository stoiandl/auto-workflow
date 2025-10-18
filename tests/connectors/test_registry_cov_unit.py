from __future__ import annotations

from auto_workflow.connectors.registry import _normalize_config_value


class Foo:
    def __init__(self):
        self.x = 1
        self.y = {"a": 2, "b": [3, 4]}


def test_normalize_config_value_covers_branches():
    # dict/list/tuple/obj paths
    v = _normalize_config_value({"k": (1, 2, [3, Foo()])})
    # Should produce serializable structure
    assert isinstance(v["k"], list)
    assert isinstance(v["k"][2], list)
    assert isinstance(v["k"][2][1], dict) and v["k"][2][1]["x"] == 1
