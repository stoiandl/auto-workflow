from __future__ import annotations

import importlib

import auto_workflow.connectors as connectors


def test_connectors_package_exports_and_imports():
    # Reload to ensure lines in __init__ execute under coverage measurement
    m = importlib.reload(connectors)
    expected = {
        "get",
        "register",
        "reset",
        "Connector",
        "BaseConnector",
        "ConnectorError",
        "TransientError",
        "PermanentError",
        "AuthError",
        "TimeoutError",
        "ConfigError",
        "NotFoundError",
    }
    assert expected.issubset(set(m.__all__))
    # Touch attributes to ensure references are resolved
    _ = (
        m.get,
        m.register,
        m.reset,
        m.Connector,
        m.BaseConnector,
        m.ConnectorError,
        m.TransientError,
        m.PermanentError,
        m.AuthError,
        m.TimeoutError,
        m.ConfigError,
        m.NotFoundError,
    )
