"""Domain-specific exceptions for auto_workflow."""

from __future__ import annotations


class AutoWorkflowError(Exception):
    """Base exception."""


class CycleDetectedError(AutoWorkflowError):
    def __init__(self, cycle: list[str]):
        super().__init__(f"Cycle detected in DAG: {' -> '.join(cycle)}")
        self.cycle = cycle


class TaskExecutionError(AutoWorkflowError):
    def __init__(self, task_name: str, original: BaseException):
        super().__init__(f"Task '{task_name}' failed: {original!r}")
        self.task_name = task_name
        self.original = original


class TimeoutError(TaskExecutionError):
    pass


class RetryExhaustedError(TaskExecutionError):
    pass


class InvalidGraphError(AutoWorkflowError):
    pass


class AggregateTaskError(AutoWorkflowError):
    """Raised when multiple tasks fail under AGGREGATE failure policy."""

    def __init__(self, errors: list[TaskExecutionError]):
        self.errors = errors
        summary = "; ".join(f"{e.task_name}: {e.original!r}" for e in errors[:5])
        more = "" if len(errors) <= 5 else f" (+{len(errors) - 5} more)"
        super().__init__(f"Multiple task failures: {summary}{more}")
