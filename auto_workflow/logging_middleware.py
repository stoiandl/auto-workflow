"""Structured logging for flows and tasks.

Provides:
- structured_logging_middleware: logs task completion (ok/err) with duration.
- register_structured_logging(): registers middleware and event subscribers to log
    flow start/completion and task start events.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import suppress
from typing import Any

from .context import get_context
from .events import subscribe

logger = logging.getLogger("auto_workflow.tasks")


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(tz=_dt.UTC).isoformat()


async def structured_logging_middleware(nxt, task_def, args, kwargs):
    ctx = None
    with suppress(Exception):  # outside flow safe
        ctx = get_context()
    start = time.time()
    meta: dict[str, Any] = {
        "task": task_def.name,
        "run_id": getattr(ctx, "run_id", None),
        "flow": getattr(ctx, "flow_name", None),
        "ts": _now_iso(),
    }
    try:
        result = await nxt()
        duration = (time.time() - start) * 1000.0
        meta["duration_ms"] = duration
        logger.info(json.dumps({"event": "task_ok", **meta}))
        return result
    except Exception as e:
        duration = (time.time() - start) * 1000.0
        meta["duration_ms"] = duration
        meta["error"] = repr(e)
        logger.error(json.dumps({"event": "task_err", **meta}))
        raise


# Event subscribers for flow/task lifecycle
def _on_flow_started(payload: dict[str, Any]) -> None:
    logger.info(
        json.dumps(
            {
                "event": "flow_started",
                "flow": payload.get("flow"),
                "run_id": payload.get("run_id"),
                "ts": _now_iso(),
            }
        )
    )


def _on_flow_completed(payload: dict[str, Any]) -> None:
    logger.info(
        json.dumps(
            {
                "event": "flow_completed",
                "flow": payload.get("flow"),
                "run_id": payload.get("run_id"),
                "tasks": payload.get("tasks"),
                "ts": _now_iso(),
            }
        )
    )


def _on_task_started(payload: dict[str, Any]) -> None:
    logger.info(
        json.dumps(
            {
                "event": "task_started",
                "task": payload.get("task"),
                "node": payload.get("node"),
                "ts": _now_iso(),
            }
        )
    )


_registered = False


def register_structured_logging() -> None:
    """Register structured logging for flow and task lifecycle.

    - Subscribes to flow_started, flow_completed, and task_started events.
    - Registers the task middleware to log completion with duration.
    """
    global _registered
    if _registered:
        return
    subscribe("flow_started", _on_flow_started)
    subscribe("flow_completed", _on_flow_completed)
    subscribe("task_started", _on_task_started)
    # Defer import to avoid cycles
    from .middleware import register as _register

    _register(structured_logging_middleware)
    _registered = True


def enable_default_logging(level: str = "INFO") -> None:
    """Attach a simple stdout handler to the auto_workflow logger if none present.

    This makes structured JSON lines visible when running scripts.
    """
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        # mark so we can replace with pretty handler if requested
        h._aw_default = True
        logger.addHandler(h)
    try:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    except Exception:
        logger.setLevel(logging.INFO)
    # Avoid duplicate propagation to root
    logger.propagate = False


class StructuredPrettyFormatter(logging.Formatter):
    def __init__(self, datefmt: str | None = None) -> None:
        super().__init__(datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        # Try to parse JSON message emitted by structured logger
        try:
            data = json.loads(record.getMessage())
        except Exception:
            return super().format(record)
        ts = self.formatTime(record, self.datefmt)
        lvl = record.levelname
        parts = [ts, lvl]
        ev = data.get("event")
        if ev:
            parts.append(ev)
        # Common fields
        kvs = []
        for k in ("flow", "run_id", "task", "node"):
            v = data.get(k)
            if v is not None:
                kvs.append(f"{k}={v}")
        if "duration_ms" in data:
            try:
                kvs.append(f"duration={float(data['duration_ms']):.1f}ms")
            except Exception:
                kvs.append(f"duration={data['duration_ms']}ms")
        if "error" in data:
            kvs.append(f"error={data['error']}")
        if kvs:
            parts.append(" ".join(kvs))
        return " | ".join(parts)


def enable_pretty_logging(level: str = "INFO") -> None:
    """Replace the default JSON-line handler with a human-friendly formatter.

    Safe to call multiple times.
    """
    # Remove our default handler if present
    new_handlers = []
    for h in logger.handlers:
        if getattr(h, "_aw_default", False):
            continue
        new_handlers.append(h)
    logger.handlers = new_handlers
    # Add pretty handler
    h = logging.StreamHandler()
    h.setFormatter(StructuredPrettyFormatter(datefmt="%Y-%m-%d %H:%M:%S%z"))
    h._aw_pretty = True
    logger.addHandler(h)
    try:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    except Exception:
        logger.setLevel(logging.INFO)
    logger.propagate = False
