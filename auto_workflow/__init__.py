"""Public API surface for auto_workflow (MVP scaffolding)."""
from .task import task, TaskDefinition
from .flow import flow, Flow
from .context import get_context
from .fanout import fan_out
from .scheduler import FailurePolicy
from .events import subscribe

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
