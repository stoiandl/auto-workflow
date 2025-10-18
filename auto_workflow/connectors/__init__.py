"""Connectors package (scaffolding).

This module provides a lightweight registry and base types for production-grade
connectors (Postgres, S3, ADLS2). Concrete connector implementations will live
in sibling modules (e.g., postgres.py, s3.py, adls2.py) and are intentionally
omitted in this scaffolding PR.

Public, stable entry points introduced here are limited to:
- get(name, profile="default") -> Connector
- register(name, factory, defaults=None)
- reset()  # testing and lifecycle

No external dependencies are introduced; this scaffolding integrates with
existing config, secrets, metrics, tracing, and events facilities.
"""

from __future__ import annotations

from .base import BaseConnector, Connector
from .exceptions import (
    AuthError,
    ConfigError,
    ConnectorError,
    NotFoundError,
    PermanentError,
    TimeoutError,
    TransientError,
)
from .registry import get, register, reset

__all__ = [
    # Registry
    "get",
    "register",
    "reset",
    # Base & types
    "Connector",
    "BaseConnector",
    # Exceptions
    "ConnectorError",
    "TransientError",
    "PermanentError",
    "AuthError",
    "TimeoutError",
    "ConfigError",
    "NotFoundError",
]
