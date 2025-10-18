from __future__ import annotations

import os

from auto_workflow.connectors.utils import apply_env_overrides, redact


def test_apply_env_overrides_and_redact(monkeypatch):
    base = {"host": "h", "password": "secret://db/password"}
    prefix = "AUTO_WORKFLOW_CONNECTORS_PG_DEFAULT__"
    monkeypatch.setenv(prefix + "PORT", "5433")
    monkeypatch.setenv(prefix + "JSON", '{"sslmode":"require","user":"u"}')

    merged = apply_env_overrides("pg", "default", base)
    # type coercion and JSON precedence
    assert merged["port"] == 5433
    assert merged["sslmode"] == "require"
    # secret:// is resolved via secrets provider; with no provider it may be None
    assert merged["password"] is None
    # redact still masks secret-looking values if shown
    assert redact("secret://anything") == "***"
    # long strings are partially masked, short strings fully masked
    assert redact("abcdefghijklmnop") == "abcd***op"
    assert redact("short") == "***"
    # non-strings mask to stars
    assert redact(1234) == "***"
