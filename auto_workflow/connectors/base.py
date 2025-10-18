"""Base interfaces and helpers for connectors.

This file defines the core Connector protocol and a small BaseConnector that
implements idempotent lifecycle and observability helpers. Concrete providers
should subclass BaseConnector or implement the Connector protocol.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from ..metrics_provider import get_metrics_provider


class Connector(Protocol):  # pragma: no cover - interface
    def open(self) -> None: ...

    def close(self) -> None: ...

    def is_closed(self) -> bool: ...

    def __enter__(self): ...

    def __exit__(self, exc_type, exc, tb): ...


@dataclass(slots=True)
class BaseConnector:
    """Minimal base implementation with idempotent lifecycle.

    Subclasses can use `_op_span` to instrument operations consistently.
    """

    name: str
    profile: str = "default"
    _closed: bool = True

    def open(self) -> None:
        self._closed = False

    def close(self) -> None:
        # Idempotent close
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    @contextmanager
    def _op_span(self, op: str, **attrs: Any):
        """Observability helper: tracing + metrics around an operation.

        Emits three metrics by convention:
        - <name>.<op>.count
        - <name>.<op>.errors
        - <name>.<op>.latency_ms
        """

        mp = get_metrics_provider()
        start = time.time()
        mp.inc(f"{self.name}.{op}.count")
        # tracer.span is async context manager in current scaffold; we cannot await here.
        # For sync connectors, we just measure duration and rely on external async span usage.
        # To keep compatibility, we don't use tracer here directly; concrete implementations
        # can integrate with async context where appropriate.
        try:
            yield
        except Exception:
            mp.inc(f"{self.name}.{op}.errors")
            raise
        finally:
            duration_ms = (time.time() - start) * 1000.0
            mp.observe(f"{self.name}.{op}.latency_ms", duration_ms)
