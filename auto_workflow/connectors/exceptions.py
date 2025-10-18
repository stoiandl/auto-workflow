"""Connector-specific error hierarchy.

All connector public APIs should raise only these errors. Underlying provider
exceptions should be wrapped and attached as __cause__ for debugging.
"""

from __future__ import annotations


class ConnectorError(RuntimeError):
    """Base connector error."""


class TransientError(ConnectorError):
    """Retryable transient error (network blips, throttling, deadlocks)."""


class PermanentError(ConnectorError):
    """Non-retryable error (syntax error, invalid parameters)."""


class AuthError(ConnectorError):
    """Authentication/authorization failure."""


class TimeoutError(ConnectorError):
    """Operation exceeded its deadline."""


class ConfigError(ConnectorError):
    """Misconfiguration (missing profile, invalid settings)."""


class NotFoundError(ConnectorError):
    """Resource not found (e.g., S3 key missing)."""
