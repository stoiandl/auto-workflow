from __future__ import annotations

import sys
from types import ModuleType

import pytest

from auto_workflow.connectors import get, reset
from auto_workflow.connectors.base import BaseConnector
from auto_workflow.connectors.exceptions import ConfigError


class Dummy(BaseConnector):
    def __init__(self, name: str, profile: str, cfg: dict):
        super().__init__(name=name, profile=profile)
        self.cfg = cfg


def test_registry_lazy_registers_via_module_attr_factory(monkeypatch):
    reset()
    modname = "auto_workflow.connectors.fakex"
    mod = ModuleType(modname)

    def factory(profile: str, cfg: dict):
        return Dummy(name="fakex", profile=profile, cfg=cfg)

    mod.FACTORY = factory  # upper-case variant
    sys.modules[modname] = mod
    try:
        c = get("fakex")
        assert isinstance(c, Dummy)
    finally:
        sys.modules.pop(modname, None)


def test_registry_raises_when_module_has_no_factory(monkeypatch):
    reset()
    modname = "auto_workflow.connectors.missingfactory"
    sys.modules[modname] = ModuleType(modname)
    try:
        with pytest.raises(ConfigError):
            _ = get("missingfactory")
    finally:
        sys.modules.pop(modname, None)
