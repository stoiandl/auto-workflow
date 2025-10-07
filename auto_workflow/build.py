"""Graph build structures: TaskInvocation & BuildContext."""
from __future__ import annotations
from dataclasses import dataclass, field
from contextvars import ContextVar
from typing import Any, Dict, List, Iterator, Iterable
import itertools


_build_ctx: ContextVar["BuildContext | None"] = ContextVar("aw_build_ctx", default=None)


@dataclass(slots=True)
class TaskInvocation:
    name: str
    task_name: str
    fn: Any
    args: tuple[Any, ...]
    kwargs: Dict[str, Any]
    definition: Any  # TaskDefinition (forward ref avoided)
    upstream: set[str] = field(default_factory=set)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskInvocation {self.name} ({self.task_name})>"

    def __hash__(self) -> int:  # allow usage inside sets during build structures
        return hash(self.name)


class BuildContext:
    def __init__(self) -> None:
        self.invocations: Dict[str, TaskInvocation] = {}
        self._counters: Dict[str, itertools.count] = {}
        self.dynamic_fanouts: list[Any] = []  # populated by fan_out for root placeholders

    def _next_id(self, task_name: str) -> str:
        if task_name not in self._counters:
            self._counters[task_name] = itertools.count(1)
        idx = next(self._counters[task_name])
        return f"{task_name}:{idx}"

    def register(self, task_name: str, fn: Any, args: tuple[Any, ...], kwargs: Dict[str, Any], definition: Any) -> TaskInvocation:
        name = self._next_id(task_name)
        inv = TaskInvocation(name=name, task_name=task_name, fn=fn, args=args, kwargs=kwargs, definition=definition)
        # Determine upstream dependencies by scanning args/kwargs
        for dep in iter_invocations((args, kwargs)):
            inv.upstream.add(dep.name)
        # Dynamic fan-out placeholder detection
        try:  # local import to avoid circular
            from .fanout import DynamicFanOut  # type: ignore
            def _scan(obj):
                if isinstance(obj, DynamicFanOut):
                    inv.upstream.add(obj._source.name)
                elif isinstance(obj, (list, tuple, set)):
                    for i in obj:
                        _scan(i)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        _scan(v)
            _scan(args)
            _scan(kwargs)
        except Exception:  # pragma: no cover
            pass
        self.invocations[name] = inv
        return inv

    def __enter__(self) -> BuildContext:
        _build_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        _build_ctx.set(None)


def current_build_context() -> BuildContext | None:
    return _build_ctx.get()


def iter_invocations(obj: Any) -> Iterator[TaskInvocation]:
    # TaskInvocation
    if isinstance(obj, TaskInvocation):
        yield obj
        for item in obj.args:
            yield from iter_invocations(item)
        for item in obj.kwargs.values():
            yield from iter_invocations(item)
        return
    # Dynamic fan-out placeholder
    try:
        from .fanout import DynamicFanOut  # type: ignore
        if isinstance(obj, DynamicFanOut):
            yield from iter_invocations(obj._source)
            for child in obj:
                yield from iter_invocations(child)
            return
    except Exception:  # pragma: no cover
        pass
    # Collections
    if isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            yield from iter_invocations(item)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_invocations(k)
            yield from iter_invocations(v)
        return
    if isinstance(obj, tuple) and len(obj) == 2 and hasattr(obj, "_fields"):  # namedtuple—approx
        for item in obj:  # pragma: no cover
            yield from iter_invocations(item)
        return
    if isinstance(obj, (bytes, str, int, float, type(None))):  # primitives
        return
    # generic container attribute iteration omitted
    return


def replace_invocations(struct: Any, results: Dict[str, Any]) -> Any:
    if isinstance(struct, TaskInvocation):
        return results[struct.name]
    if isinstance(struct, list):
        return [replace_invocations(s, results) for s in struct]
    if isinstance(struct, tuple):
        return tuple(replace_invocations(s, results) for s in struct)
    if isinstance(struct, set):
        return {replace_invocations(s, results) for s in struct}
    if isinstance(struct, dict):
        return {replace_invocations(k, results): replace_invocations(v, results) for k, v in struct.items()}
    return struct


def collect_invocations(struct: Any) -> List[TaskInvocation]:
    seen: Dict[str, TaskInvocation] = {}
    for inv in iter_invocations(struct):
        seen[inv.name] = inv
    return list(seen.values())


def _inject_cycle(a: TaskInvocation, b: TaskInvocation) -> None:  # pragma: no cover - test utility
    """Force a cycle between two invocations for testing cycle detection."""
    a.upstream.add(b.name)
    b.upstream.add(a.name)
