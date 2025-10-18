from __future__ import annotations

import os

import pytest

from auto_workflow.env_overrides import apply_env_overrides
from auto_workflow.secrets import StaticMappingSecrets, set_secrets_provider


def test_no_env_returns_base(monkeypatch):
    base = {"a": 1, "nested": {"x": 2}}
    # Ensure no variables of our prefix are present
    for k in list(os.environ.keys()):
        if k.startswith("AW_TEST__"):
            monkeypatch.delenv(k, raising=False)
    out = apply_env_overrides("AW_TEST__", base, resolve_secrets=False)
    assert out == base


def test_individual_keys_merge_and_lowercase(monkeypatch):
    base = {"Pool": {"Min_Size": 1}}
    monkeypatch.setenv("AW_MERGE__POOL__MAX_SIZE", "10")
    monkeypatch.setenv("AW_MERGE__NewKey", "val")
    out = apply_env_overrides("AW_MERGE__", base, resolve_secrets=False)
    # Original keys preserved as-is; env overlay uses lower-case
    assert out["Pool"]["Min_Size"] == 1
    assert out["pool"]["max_size"] == 10
    assert out["newkey"] == "val"


@pytest.mark.parametrize(
    "env_val, expected",
    [
        ("true", True),
        ("FALSE", False),
        ("42", 42),
        ("-7", -7),
        ("3.14", 3.14),
        ("100ms", 0.1),
        ("2s", 2.0),
        ("5m", 300.0),
    ],
)
def test_type_coercions(monkeypatch, env_val, expected):
    base = {}
    monkeypatch.setenv("AW_TYPES__X", env_val)
    out = apply_env_overrides("AW_TYPES__", base, resolve_secrets=False)
    if isinstance(expected, float):
        assert out["x"] == pytest.approx(expected)
    else:
        assert out["x"] == expected


def test_json_overlay_precedence_and_addition(monkeypatch):
    base = {"a": 1}
    monkeypatch.setenv("AW_JSON__A", "2")
    monkeypatch.setenv("AW_JSON__JSON", '{"a": 3, "b": true}')
    out = apply_env_overrides("AW_JSON__", base, resolve_secrets=False)
    assert out["a"] == 3  # JSON wins
    assert out["b"] is True  # added via JSON


def test_malformed_json_is_ignored(monkeypatch):
    base = {"a": 1}
    monkeypatch.setenv("AW_BADJSON__A", "2")
    monkeypatch.setenv("AW_BADJSON__JSON", "{not-json}")
    out = apply_env_overrides("AW_BADJSON__", base, resolve_secrets=False)
    assert out["a"] == 2  # falls back to individual key


def test_secret_resolution_by_scheme_and_keys(monkeypatch):
    set_secrets_provider(
        StaticMappingSecrets(
            {
                "DB_PASSWORD": "p@ss",
                "TOKEN": "tok",
            }
        )
    )
    base = {"password": None, "nested": {"credential": None, "other": None}}
    # Scheme-based
    monkeypatch.setenv("AW_SEC__PASSWORD", "secret://DB_PASSWORD")
    # Value without scheme should remain literal even for secret-named key
    monkeypatch.setenv("AW_SEC__NESTED__CREDENTIAL", "TOKEN")
    # Non-secret key with secret-looking value should not resolve without scheme
    monkeypatch.setenv("AW_SEC__NESTED__OTHER", "SHOULD_NOT_RESOLVE")

    out = apply_env_overrides(
        "AW_SEC__",
        base,
        resolve_secrets=True,
        secret_keys=("password", "credential"),
    )
    assert out["password"] == "p@ss"
    assert out["nested"]["credential"] == "TOKEN"
    assert out["nested"]["other"] == "SHOULD_NOT_RESOLVE"


def test_secret_resolution_in_json_overlay(monkeypatch):
    set_secrets_provider(StaticMappingSecrets({"API_KEY": "abc"}))
    base = {}
    # JSON with secret scheme value
    monkeypatch.setenv("AW_JSONSEC__JSON", '{"key": "secret://API_KEY"}')
    out = apply_env_overrides("AW_JSONSEC__", base, resolve_secrets=True, secret_keys=("key",))
    assert out["key"] == "abc"
