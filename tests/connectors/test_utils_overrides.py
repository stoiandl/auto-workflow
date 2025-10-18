from __future__ import annotations

from auto_workflow.connectors.utils import apply_env_overrides


def test_env_overrides_and_coercions(monkeypatch):
    base = {"pool": {"min_size": 1}, "statement_timeout_ms": 1000}
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_PG_DEFAULT__POOL__MAX_SIZE", "10")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_PG_DEFAULT__STATEMENT_TIMEOUT_MS", "30s")
    out = apply_env_overrides("pg", "default", base)
    assert out["pool"]["max_size"] == 10
    # duration coerced to seconds
    assert out["statement_timeout_ms"] == 30.0


def test_json_overlay_precedence(monkeypatch):
    base = {"a": 1}
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_X_DEFAULT__A", "2")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_X_DEFAULT__JSON", '{"a": 3, "b": true}')
    out = apply_env_overrides("x", "default", base)
    assert out["a"] == 3
    assert out["b"] is True
