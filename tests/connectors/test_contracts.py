from __future__ import annotations

from auto_workflow.connectors.base import BaseConnector


def test_base_connector_lifecycle():
    c = BaseConnector(name="test")
    assert c.is_closed() is True
    with c as cc:
        assert cc is c
        assert c.is_closed() is False
    assert c.is_closed() is True


def test_observability_helpers_increment_metrics(monkeypatch):
    # Use a simple capture for metrics
    observed = {"inc": [], "obs": []}

    class MP:
        def inc(self, name: str, value: float = 1.0, **labels):
            observed["inc"].append(name)

        def observe(self, name: str, value: float, **labels):
            observed["obs"].append(name)

    from auto_workflow.metrics_provider import set_metrics_provider

    set_metrics_provider(MP())

    c = BaseConnector(name="alpha")
    try:
        with c._op_span("ping"):
            pass
    except Exception:  # pragma: no cover - not expected
        raise AssertionError("_op_span should not raise for no-op") from None

    assert "alpha.ping.count" in observed["inc"]
    assert "alpha.ping.latency_ms" in observed["obs"]
