from __future__ import annotations

import importlib

import auto_workflow.connectors as connectors_pkg


def test_connectors_init_exports_reload():
    # Reload to ensure coverage captures module body
    mod = importlib.reload(connectors_pkg)
    # Exposed API should be present
    assert hasattr(mod, "get") and callable(mod.get)
    assert hasattr(mod, "register") and callable(mod.register)
    assert hasattr(mod, "reset") and callable(mod.reset)
    # Exceptions
    for name in (
        "ConnectorError",
        "TransientError",
        "PermanentError",
        "AuthError",
        "TimeoutError",
        "ConfigError",
        "NotFoundError",
    ):
        assert hasattr(mod, name)
