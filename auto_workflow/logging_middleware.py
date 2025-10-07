"""Structured logging middleware for tasks."""
from __future__ import annotations
import time, json, logging
from typing import Any, Dict
from .context import get_context

logger = logging.getLogger("auto_workflow.tasks")

async def structured_logging_middleware(nxt, task_def, args, kwargs):
    ctx = None
    try:
        ctx = get_context()
    except Exception:  # outside flow
        pass
    start = time.time()
    meta: Dict[str, Any] = {
        "task": task_def.name,
        "run_id": getattr(ctx, "run_id", None),
        "flow": getattr(ctx, "flow_name", None),
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
