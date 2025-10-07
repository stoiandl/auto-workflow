"""Execution context handling."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RunContext:
    run_id: str
    flow_name: str
    start_time: float = field(default_factory=time.time)
    params: dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("auto_workflow"))


_current_context: ContextVar[RunContext | None] = ContextVar("auto_workflow_run_ctx", default=None)


def set_context(ctx: RunContext) -> None:
    _current_context.set(ctx)


def get_context() -> RunContext:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("No active RunContext; are you inside a flow execution?")
    return ctx
