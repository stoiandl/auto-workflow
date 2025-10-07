"""Fan-out helper utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .build import TaskInvocation, current_build_context


class DynamicFanOut(list):  # placeholder container recognized by scheduler
    def __init__(
        self,
        task_def,
        source_invocation: TaskInvocation | DynamicFanOut,
        max_concurrency: int | None,
        ctx,
    ):
        super().__init__()
        self._task_def = task_def
        self._source = source_invocation
        self._max_conc = max_concurrency
        self._expanded = False
        self._ctx = ctx

    def expand(self, values: Iterable[Any]):
        if self._expanded:
            return
        for v in values:
            self.append(
                self._ctx.register(self._task_def.name, self._task_def.fn, (v,), {}, self._task_def)
            )
        self._expanded = True


def fan_out(task_def, iterable: Iterable[Any], *, max_concurrency: int | None = None) -> list[Any]:
    """Create multiple task invocations from an iterable.

    max_concurrency is reserved for future scheduling throttling; currently unused.
    """
    ctx = current_build_context()
    out = []
    if ctx is None:
        # immediate execution path
        return [task_def(item) for item in iterable]
    from .fanout import DynamicFanOut  # self-import safe

    if isinstance(iterable, TaskInvocation):  # dynamic runtime fan-out
        df = DynamicFanOut(task_def, iterable, max_concurrency, ctx)
        ctx.dynamic_fanouts.append(df)
        return df
    if isinstance(iterable, DynamicFanOut):  # nested dynamic
        # nested placeholder - track as root only if original source TaskInvocation (first-level)
        df = DynamicFanOut(task_def, iterable, max_concurrency, ctx)
        ctx.dynamic_fanouts.append(df)
        return df
    for item in iterable:
        out.append(task_def(item))
    return out
