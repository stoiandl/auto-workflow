"""Flow abstraction and decorator."""
from __future__ import annotations
import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .context import RunContext, set_context
from .executors.async_executor import AsyncExecutor
from .executors.thread_executor import ThreadExecutor
from .executors.process_executor import ProcessExecutor
from .build import BuildContext, collect_invocations, replace_invocations
from .scheduler import execute_dag, FailurePolicy
from .config import load_config
from .events import emit
from .tracing import get_tracer

@dataclass(slots=True)
class Flow:
    name: str
    build_fn: Callable[..., Any]

    async def _run_internal(self, *args: Any, executor: str = "async", params: Optional[Dict[str, Any]] = None,
                             failure_policy: str = FailurePolicy.FAIL_FAST, max_concurrency: int | None = None,
                             **kwargs: Any) -> Any:
        cfg = load_config()
        if max_concurrency is None:
            max_concurrency = cfg.get("max_dynamic_tasks")
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
        # Execute via scheduler (currently ignores executor selection for CPU-bound vs async differentiation)
        results = await execute_dag(invocations, failure_policy=failure_policy, max_concurrency=max_concurrency, dynamic_roots=dynamic_roots)  # type: ignore
        emit("flow_completed", {"flow": self.name, "run_id": ctx.run_id, "tasks": len(invocations)})
        return replace_invocations(structure, results)

    def run(self, *args: Any, executor: str = "async", params: Optional[Dict[str, Any]] = None,
            failure_policy: str = FailurePolicy.FAIL_FAST, max_concurrency: int | None = None, **kwargs: Any) -> Any:
        return asyncio.run(self._run_internal(*args, executor=executor, params=params,
                                             failure_policy=failure_policy, max_concurrency=max_concurrency, **kwargs))

    def describe(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the DAG that would be built.
        Does not execute any tasks.
        """
        with BuildContext() as bctx:
            structure = self.build_fn(*args, **kwargs)
            dyn_placeholders = list(bctx.dynamic_fanouts)
        invocations = collect_invocations(structure)
        # Attach a synthetic upstream hint for nodes consuming dynamic placeholders
        from .fanout import DynamicFanOut
        for inv in invocations:
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    # depend on source invocation so scheduling waits for expansion -> children edges injected later
                    src = arg._source
                    if hasattr(src, 'name'):
                        inv.upstream.add(getattr(src, 'name'))
        nodes = []
        for inv in invocations:
            nodes.append({
                "id": inv.name,
                "task": inv.task_name,
                "upstream": sorted(inv.upstream),
                "persist": getattr(inv.definition, "persist", False),
                "run_in": getattr(inv.definition, "run_in", "async"),
                "retries": getattr(inv.definition, "retries", 0),
            })
        return {
            "flow": self.name,
            "nodes": nodes,
            "count": len(nodes),
        }

    def export_dot(self, *args: Any, **kwargs: Any) -> str:
        from .dag import DAG
        with BuildContext() as bctx:
            structure = self.build_fn(*args, **kwargs)
        invocations = collect_invocations(structure)
        from .fanout import DynamicFanOut
        # ensure upstream dependency on dynamic source(s)
        for inv in invocations:
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    src = arg._source
                    if hasattr(src, 'name'):
                        inv.upstream.add(getattr(src, 'name'))
        dag = DAG()
        for inv in invocations:
            dag.add_node(inv.name)
            for up in inv.upstream:
                dag.add_edge(up, inv.name)
        return dag.to_dot()

    def export_graph(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        from .dag import DAG
        with BuildContext() as bctx:
            structure = self.build_fn(*args, **kwargs)
        invocations = collect_invocations(structure)
        dag = DAG()
        for inv in invocations:
            dag.add_node(inv.name)
            for up in inv.upstream:
                dag.add_edge(up, inv.name)
        return dag.to_dict()


def flow(_fn: Optional[Callable[..., Any]] = None, *, name: Optional[str] = None) -> Callable[[Callable[..., Any]], Flow]:
    def wrap(fn: Callable[..., Any]) -> Flow:
        return Flow(name=name or fn.__name__, build_fn=fn)
    if _fn is not None:
        return wrap(_fn)
    return wrap
