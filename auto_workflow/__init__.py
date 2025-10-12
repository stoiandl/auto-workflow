"""Public API surface for auto_workflow (MVP scaffolding)."""

try:  # pragma: no cover - best-effort version exposure
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("auto-workflow")
except Exception:  # pragma: no cover
    __version__ = "0"

from .context import get_context
from .events import subscribe
from .fanout import fan_out
from .flow import Flow, flow
from .scheduler import FailurePolicy
from .task import TaskDefinition, task

# Enable structured pretty logging by default unless explicitly disabled via env
try:  # pragma: no cover - import side-effect
    import os

    if os.environ.get("AUTO_WORKFLOW_DISABLE_STRUCTURED_LOGS", "0") not in ("1", "true", "True"):
        from .logging_middleware import enable_pretty_logging, register_structured_logging

        register_structured_logging()
        # Always attach the pretty handler by default
        enable_pretty_logging(os.environ.get("AUTO_WORKFLOW_LOG_LEVEL", "INFO"))
except Exception:
    # Never fail import due to logging setup
    pass

__all__ = [
    "task",
    "TaskDefinition",
    "flow",
    "Flow",
    "get_context",
    "fan_out",
    "FailurePolicy",
    "subscribe",
]
