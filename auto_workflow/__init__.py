"""Public API surface for auto_workflow (MVP scaffolding)."""

from .context import get_context
from .events import subscribe
from .fanout import fan_out
from .flow import Flow, flow
from .scheduler import FailurePolicy
from .task import TaskDefinition, task

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
