from __future__ import annotations

from auto_workflow.connectors import ConfigError, get, register, reset
from auto_workflow.connectors.base import BaseConnector


class Dummy(BaseConnector):
    cfg: dict

    def __init__(self, name: str, profile: str, cfg: dict):
        super().__init__(name=name, profile=profile)
        self.cfg = cfg


def _dummy_factory(profile: str, cfg: dict):
    return Dummy(name="dummy", profile=profile, cfg=cfg)


def setup_function(_):
    reset()


def test_unregistered_raises():
    try:
        get("missing")
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError")


def test_register_and_get_caches(monkeypatch):
    register("dummy", _dummy_factory)
    # base config via env overlay
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_DUMMY_DEFAULT__X", "1")
    c1 = get("dummy")
    assert isinstance(c1, Dummy)
    assert c1.cfg["x"] == 1
    c2 = get("dummy")
    assert c1 is c2  # cached
    # Close should drop from cache on next get
    c1.close()
    c3 = get("dummy")
    assert c3 is not c1


def test_json_overlay_beats_individual(monkeypatch):
    register("dummy", _dummy_factory)
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_DUMMY_DEFAULT__X", "1")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_DUMMY_DEFAULT__JSON", '{"x": 2, "y": true}')
    c = get("dummy")
    assert c.cfg["x"] == 2
    assert c.cfg["y"] is True
