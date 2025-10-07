"""Tracing scaffold (OpenTelemetry friendly)."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
import time

class DummyTracer:
    @asynccontextmanager
    async def span(self, name: str, **attrs: Any):  # pragma: no cover simple scaffold
        start = time.time()
        try:
            yield {"start": start, "name": name, **attrs}
        finally:
            _ = time.time() - start

_tracer: DummyTracer = DummyTracer()

def get_tracer() -> DummyTracer:
    return _tracer

def set_tracer(t: DummyTracer) -> None:
    global _tracer
    _tracer = t
