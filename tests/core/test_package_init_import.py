import importlib
import sys


def test_init_import_side_effect_guard(monkeypatch):
    # Disable structured logs so import path avoids setting up pretty logs
    monkeypatch.setenv("AUTO_WORKFLOW_DISABLE_STRUCTURED_LOGS", "1")
    if "auto_workflow" in sys.modules:
        del sys.modules["auto_workflow"]
    mod = importlib.import_module("auto_workflow")
    # Access a couple of exported names
    assert hasattr(mod, "task") and hasattr(mod, "flow")
