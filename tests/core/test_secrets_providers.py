import os

from auto_workflow.secrets import EnvSecrets, StaticMappingSecrets, secret, set_secrets_provider


def test_env_secrets(monkeypatch):
    monkeypatch.setenv("AW_TOKEN", "abc")
    set_secrets_provider(EnvSecrets())
    assert secret("AW_TOKEN") == "abc"


def test_static_mapping_secrets():
    set_secrets_provider(StaticMappingSecrets({"X": "1"}))
    assert secret("X") == "1"
    assert secret("Y") is None
