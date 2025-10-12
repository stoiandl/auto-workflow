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
        # Execute via scheduler
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
        params: dict[str, Any] | None = None,
        failure_policy: str = FailurePolicy.FAIL_FAST,
        max_concurrency: int | None = None,
        **kwargs: Any,
    ) -> Any:
        return asyncio.run(
            self._run_internal(
                *args,
                params=params,
                failure_policy=failure_policy,
                max_concurrency=max_concurrency,
                **kwargs,
            )
        )

    def describe(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Return a JSON-serializable representation of the DAG that would be built.
        Does not execute any tasks. Includes dynamic fan-out placeholders as explicit
        barrier nodes so downstream dependencies are clear, including nested fan-outs.
        """
        from .fanout import DynamicFanOut

        # Build and capture dynamic placeholders
        with BuildContext() as bctx:
            structure = self.build_fn(*args, **kwargs)
            dynamic_placeholders = list(bctx.dynamic_fanouts)

        invocations = collect_invocations(structure)

        # Map each DynamicFanOut instance to a stable id and gather consumers
        fanout_id_map: dict[int, str] = {}
        fanout_info: dict[str, dict[str, Any]] = {}

        for idx, df in enumerate(dynamic_placeholders, start=1):
            fid = f"fanout:{idx}"
            fanout_id_map[id(df)] = fid
            # Determine source identifier (invocation name or parent fanout id)
            if hasattr(df._source, "name"):
                source_id = df._source.name
            else:
                # Nested: source is another DynamicFanOut
                source_id = fanout_id_map.get(id(df._source), "<unknown>")
            fanout_info[fid] = {
                "id": fid,
                "type": "dynamic_fanout",
                "task": getattr(df._task_def, "name", "<unknown>"),
                "source": source_id,
                "max_concurrency": df._max_conc,
                "consumers": [],
            }

        # Scan invocations to find consumers of each dynamic placeholder and
        # rewire their upstream to depend on the fanout barrier instead of the raw source
        for inv in invocations:
            args_and_kwargs = list(inv.args) + list(inv.kwargs.values())
            for arg in args_and_kwargs:
                if isinstance(arg, DynamicFanOut):
                    fid = fanout_id_map.get(id(arg))
                    if not fid:
                        # Placeholder may not have been recorded (unlikely); skip
                        continue
                    fi = fanout_info[fid]
                    fi["consumers"].append(inv.name)

        # Build adjacency for transitive propagation (name -> list of consumers)
        consumers_by_name: dict[str, list[str]] = {}
        for inv in invocations:
            for up in inv.upstream:
                consumers_by_name.setdefault(up, []).append(inv.name)

        # Precompute full set of transitive consumers per fanout barrier
        transitive_consumers: dict[str, set[str]] = {}
        for fid, info in fanout_info.items():
            seen: set[str] = set()
            work: list[str] = list(info["consumers"])  # start from direct consumers
            while work:
                cur = work.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for nxt in consumers_by_name.get(cur, []):
                    if nxt not in seen:
                        work.append(nxt)
            transitive_consumers[fid] = seen

        # Now construct node list with effective upstream including fanout barriers
        nodes: list[dict[str, Any]] = []
        for inv in invocations:
            effective_up: set[str] = set(inv.upstream)
            # Replace dynamic sources with fanout barrier id (direct consumers)
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    fid = fanout_id_map.get(id(arg))
                    if hasattr(arg._source, "name"):
                        effective_up.discard(arg._source.name)
                    if fid:
                        effective_up.add(fid)
            # Add transitive fanout dependencies
            for fid, reached in transitive_consumers.items():
                if inv.name in reached:
                    effective_up.add(fid)

            nodes.append(
                {
                    "id": inv.name,
                    "task": inv.task_name,
                    "upstream": sorted(effective_up),
                    "persist": getattr(inv.definition, "persist", False),
                    "run_in": getattr(inv.definition, "run_in", "async"),
                    "retries": getattr(inv.definition, "retries", 0),
                }
            )

        dynamic_fanouts = list(fanout_info.values())
        return {
            "flow": self.name,
            "nodes": nodes,
            "dynamic_fanouts": dynamic_fanouts,
            "count": len(nodes),
            "dynamic_count": len(dynamic_fanouts),
        }

    def export_dot(self, *args: Any, **kwargs: Any) -> str:
        from .dag import DAG
        from .fanout import DynamicFanOut

        # Build and capture dynamic placeholders
        with BuildContext() as bctx:
            structure = self.build_fn(*args, **kwargs)
            dynamic_placeholders = list(bctx.dynamic_fanouts)
        invocations = collect_invocations(structure)

        # Assign ids to fanouts and create DAG nodes
        dag = DAG()
        fanout_id_map: dict[int, str] = {}

        for idx, df in enumerate(dynamic_placeholders, start=1):
            fid = f"fanout:{idx}"
            fanout_id_map[id(df)] = fid
            label = f"fan_out({getattr(df._task_def, 'name', '<unknown>')})"
            dag.add_node(fid, shape="diamond", label=label, color="lightblue")

        # Wire edges: source -> fanout
        for df in dynamic_placeholders:
            fid = fanout_id_map[id(df)]
            if hasattr(df._source, "name"):
                dag.add_edge(df._source.name, fid)
            else:
                # Nested: parent is another fanout
                parent = fanout_id_map.get(id(df._source))
                if parent:
                    dag.add_edge(parent, fid)

        # Add invocation nodes and wire upstream using fanout barriers where applicable
        for inv in invocations:
            dag.add_node(inv.name)
            effective_up: set[str] = set(inv.upstream)
            for arg in list(inv.args) + list(inv.kwargs.values()):
                if isinstance(arg, DynamicFanOut):
                    # Replace raw source with fanout barrier id
                    if hasattr(arg._source, "name"):
                        effective_up.discard(arg._source.name)
                    fid = fanout_id_map.get(id(arg))
                    if fid:
                        effective_up.add(fid)
                        # Ensure edge fanout -> consumer exists
                        dag.add_edge(fid, inv.name)
            for up in sorted(effective_up):
                # Avoid duplicating edges already added for fanout -> consumer
                if up not in fanout_id_map.values():
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
