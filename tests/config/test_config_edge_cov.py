from __future__ import annotations

import importlib
import os

import pytest

import auto_workflow.config as cfg_mod


def test_config_load_defaults_and_env_guard(monkeypatch):
    # Ensure no config file present and env overlays minimal
    monkeypatch.delenv("AUTO_WORKFLOW_CONFIG", raising=False)
    monkeypatch.delenv("AUTO_WORKFLOW_CONFIG_JSON", raising=False)
    # Reload to ensure import-level branches get covered
    m = importlib.reload(cfg_mod)
    # Basic call should not raise and return dict
    c = m.load_config()
    assert isinstance(c, dict)
