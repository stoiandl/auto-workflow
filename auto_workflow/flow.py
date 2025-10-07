"""Flow abstraction and decorator."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .build import BuildContext, collect_invocations, replace_invocations
from .config import load_config
from .context import RunContext, set_context
from .events import emit
from .scheduler import FailurePolicy, execute_dag
from .tracing import get_tracer


@dataclass(slots=True)
class Flow:
    name: str
    build_fn: Callable[..., Any]

    async def _run_internal(
        self,
        *args: Any,
        executor: str = "async",
        params: dict[str, Any] | None = None,
        failure_policy: str = FailurePolicy.FAIL_FAST,
        max_concurrency: int | None = None,
        **kwargs: Any,
    ) -> Any:
        cfg = load_config()
        if max_concurrency is None:
            mc = cfg.get("max_dynamic_tasks")
            if isinstance(mc, str):
                if mc.isdigit():
                    try:
                        mc = int(mc)
                    except ValueError:  # pragma: no cover
                        mc = None
                else:
                    mc = None  # non-numeric string -> ignore
            max_concurrency = mc if isinstance(mc, int) and mc > 0 else None
        ctx = RunContext(run_id=str(uuid.uuid4()), flow_name=self.name, params=params or {})
        set_context(ctx)
        tracer = get_tracer()
        emit("flow_started", {"flow": self.name, "run_id": ctx.run_id})
        async with tracer.span(f"flow:{self.name}", run_id=ctx.run_id):
            with BuildContext() as bctx:
                structure = self.build_fn(*args, **kwargs)
                dynamic_roots = list(bctx.dynamic_fanouts)
            invocations = collect_invocations(structure)
        if not invocations:
            # trivial, return original structure (no tasks used)
            emit("flow_completed", {"flow": self.name, "run_id": ctx.run_id, "tasks": 0})
            return structure
        # Execute via scheduler (executor selection for CPU vs async currently ignored)
        results = await execute_dag(
            invocations,
            failure_policy=failure_policy,
            max_concurrency=max_concurrency,
            dynamic_roots=dynamic_roots,
        )  # type: ignore
        emit("flow_completed", {"flow": self.name, "run_id": ctx.run_id, "tasks": len(invocations)})
        return replace_invocations(structure, results)

    def run(
        self,
        *args: Any,
        executor: str = "async",
        params: dict[str, Any] | None = None,
        failure_policy: str = FailurePolicy.FAIL_FAST,
        max_concurrency: int | None = None,
        **kwargs: Any,
    ) -> Any:
        return asyncio.run(
            self._run_internal(
                *args,
                executor=executor,
                params=params,
                failure_policy=failure_policy,
                max_concurrency=max_concurrency,
                **kwargs,
            )
        )

    def describe(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Return a JSON-serializable representation of the DAG that would be built.
        Does not execute any tasks.
        """
        with BuildContext():
            structure = self.build_fn(*args, **kwargs)
        invocations = collect_invocations(structure)
        # Attach a synthetic upstream hint for nodes consuming dynamic placeholders
        from .fanout import DynamicFanOut

        for inv in invocations:
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    # depend on source invocation so scheduling waits for expansion
                    # children edges injected later
                    src = arg._source
                    if hasattr(src, "name"):
                        inv.upstream.add(src.name)
        nodes = []
        for inv in invocations:
            nodes.append(
                {
                    "id": inv.name,
                    "task": inv.task_name,
                    "upstream": sorted(inv.upstream),
                    "persist": getattr(inv.definition, "persist", False),
                    "run_in": getattr(inv.definition, "run_in", "async"),
                    "retries": getattr(inv.definition, "retries", 0),
                }
            )
        return {
            "flow": self.name,
            "nodes": nodes,
            "count": len(nodes),
        }

    def export_dot(self, *args: Any, **kwargs: Any) -> str:
        from .dag import DAG

        with BuildContext():
            structure = self.build_fn(*args, **kwargs)
        invocations = collect_invocations(structure)
        from .fanout import DynamicFanOut

        # ensure upstream dependency on dynamic source(s)
        for inv in invocations:
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    src = arg._source
                    if hasattr(src, "name"):
                        inv.upstream.add(src.name)
        dag = DAG()
        for inv in invocations:
            dag.add_node(inv.name)
            for up in inv.upstream:
                dag.add_edge(up, inv.name)
        return dag.to_dot()

    def export_graph(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from .dag import DAG

        with BuildContext():
            structure = self.build_fn(*args, **kwargs)
        invocations = collect_invocations(structure)
        dag = DAG()
        for inv in invocations:
            dag.add_node(inv.name)
            for up in inv.upstream:
                dag.add_edge(up, inv.name)
        return dag.to_dict()


def flow(
    _fn: Callable[..., Any] | None = None, *, name: str | None = None
) -> Callable[[Callable[..., Any]], Flow]:
    def wrap(fn: Callable[..., Any]) -> Flow:
        return Flow(name=name or fn.__name__, build_fn=fn)

    if _fn is not None:
        return wrap(_fn)
    return wrap
