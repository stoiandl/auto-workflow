"""Simple topological scheduler executing TaskInvocations respecting dependencies."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .artifacts import get_store
from .build import TaskInvocation
from .cache import get_result_cache
from .dag import DAG
from .events import emit
from .exceptions import AggregateTaskError, TaskExecutionError
from .metrics_provider import get_metrics_provider
from .middleware import get_task_middleware_chain
from .tracing import get_tracer


class InMemoryResultCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, ttl: int | None) -> Any | None:
        if ttl is None:
            return None
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts <= ttl:
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)


class FailurePolicy:
    FAIL_FAST = "fail_fast"
    CONTINUE = "continue"
    AGGREGATE = "aggregate"


async def execute_dag(
    invocations: list[TaskInvocation],
    *,
    failure_policy: str = FailurePolicy.FAIL_FAST,
    max_concurrency: int | None = None,
    cancel_event: asyncio.Event | None = None,
    dynamic_roots: list[Any] | None = None,
) -> dict[str, Any]:
    dag = DAG()
    for inv in invocations:
        dag.add_node(inv.name)
        for up in inv.upstream:
            dag.add_edge(up, inv.name)
    order = dag.topological_sort()
    inv_map = {inv.name: inv for inv in invocations}
    results: dict[str, Any] = {}
    cache = get_result_cache()
    # simple ready set processing
    remaining_deps = {name: set(inv_map[name].upstream) for name in order}
    ready = [n for n, deps in remaining_deps.items() if not deps]
    # removed unused 'running' variable
    pending_tasks: dict[str, asyncio.Task[Any]] = {}

    sem = asyncio.Semaphore(max_concurrency or len(order))
    task_errors: list[TaskExecutionError] = []

    # For tasks with cache_ttl we may have multiple identical invocations ready simultaneously
    # (e.g., synchronous functions now offloaded to threads). Use an in-flight map to deduplicate.
    inflight: dict[str, asyncio.Future[Any]] = {}

    async def schedule(name: str) -> None:
        inv = inv_map[name]
        # prepare args by replacing dependencies
        resolved_args = _hydrate(inv.args, results)
        resolved_kwargs = _hydrate(inv.kwargs, results)
        # caching (per task definition attributes)
        cache_ttl = getattr(inv.definition, "cache_ttl", None)
        cache_key = inv.definition.cache_key(*resolved_args, **resolved_kwargs)
        if cache_ttl is not None:
            cached = cache.get(cache_key, cache_ttl)
            if cached is not None:
                results[name] = cached
                return
            # Dedup: if another identical task already running, await its future
            existing = inflight.get(cache_key)
            if existing is not None:
                try:
                    value = await existing
                except Exception as e:  # propagate underlying failure
                    raise e
                results[name] = value
                return
        try:
            emit("task_started", {"task": inv.task_name, "node": name})
            start = time.time()
            async with sem:
                tracer = get_tracer()
                async with tracer.span(f"task:{inv.task_name}", node=name):

                    async def core_run():
                        return await inv.definition.run(*resolved_args, **resolved_kwargs)

                    # apply middleware chain (wrap before marking inflight for accuracy)
                    if cache_ttl is not None and cache_key not in inflight:
                        # register future placeholder before execution so followers can await
                        inflight[cache_key] = asyncio.get_running_loop().create_future()
                    value = await get_task_middleware_chain()(
                        core_run, inv.definition, resolved_args, resolved_kwargs
                    )
            duration = time.time() - start
            # artifact persistence if requested
            if getattr(inv.definition, "persist", False):
                store = get_store()
                ref = store.put(value)
                value = ref
            results[name] = value
            if cache_ttl is not None:
                cache.set(cache_key, value)
                fut = inflight.get(cache_key)
                if fut and not fut.done():
                    fut.set_result(value)
                inflight.pop(cache_key, None)
            emit(
                "task_succeeded",
                {"task": inv.task_name, "node": name, "duration_ms": duration * 1000.0},
            )
            mp = get_metrics_provider()
            mp.inc("tasks_succeeded")
            mp.observe("task_duration_ms", duration * 1000.0)
        except Exception as e:  # noqa: BLE001
            te = TaskExecutionError(inv.task_name, e)
            if cache_ttl is not None:
                fut = inflight.get(cache_key)
                if fut and not fut.done():
                    fut.set_exception(e)
                inflight.pop(cache_key, None)
            if failure_policy == FailurePolicy.FAIL_FAST:
                emit("task_failed", {"task": inv.task_name, "node": name, "error": repr(e)})
                # record failure result so downstream inspection doesn't KeyError before propagation
                results[name] = te
                mp = get_metrics_provider()
                mp.inc("tasks_failed")
                raise te from None
            task_errors.append(te)
            results[name] = te
            emit("task_failed", {"task": inv.task_name, "node": name, "error": repr(e)})
            mp = get_metrics_provider()
            mp.inc("tasks_failed")

    # Map consumer invocation name -> list of DynamicFanOut placeholders it references
    from .fanout import DynamicFanOut

    consumer_placeholders: dict[str, list[DynamicFanOut]] = {}
    all_placeholders: list[DynamicFanOut] = []
    if dynamic_roots:
        for p in dynamic_roots:
            if isinstance(p, DynamicFanOut):
                all_placeholders.append(p)
    for inv in invocations:
        for arg in list(inv.args) + list(inv.kwargs.values()):
            if isinstance(arg, DynamicFanOut):
                consumer_placeholders.setdefault(inv.name, []).append(arg)
                all_placeholders.append(arg)

    while ready or pending_tasks:
        if cancel_event and cancel_event.is_set():
            # Cancel all running tasks
            for t in pending_tasks.values():
                t.cancel()
            # Wait for cancellation to propagate
            if pending_tasks:
                await asyncio.gather(*pending_tasks.values(), return_exceptions=True)
            break
        # Determine which ready nodes are truly runnable (no unexpanded placeholders they depend on)
        runnable: list[str] = []
        for node in list(ready):
            placeholders = consumer_placeholders.get(node, [])
            gate = False
            for p in placeholders:
                # Need expansion complete and all child results materialized
                if (not p._expanded) or any(child.name not in results for child in p):
                    gate = True
                    break
            if gate:
                continue
            runnable.append(node)
        # Enforce priority ordering (higher priority scheduled first)
        runnable.sort(key=lambda n: getattr(inv_map[n].definition, "priority", 0), reverse=True)
        for node in runnable:
            # Skip if already scheduled (defensive against accidental duplicates in ready)
            if node in pending_tasks:
                # Remove duplicate occurrence
                ready.remove(node)
                continue
            ready.remove(node)
            pending_tasks[node] = asyncio.create_task(schedule(node))
        if not pending_tasks:
            break
        done, _ = await asyncio.wait(pending_tasks.values(), return_when=asyncio.FIRST_COMPLETED)
        finished_names = [n for n, t in list(pending_tasks.items()) if t in done]
        for fname in finished_names:
            task = pending_tasks.pop(fname)
            exc = task.exception()
            if exc:
                raise exc
            # After task success, check if any dynamic fan-outs depend on it
            from .fanout import DynamicFanOut

            # Evaluate expansion conditions for all placeholders (supports nesting)
            for placeholder in list(all_placeholders):
                if placeholder._expanded:
                    continue
                src = placeholder._source
                ready_to_expand = False
                if isinstance(src, TaskInvocation) and src.name == fname:
                    ready_to_expand = True
                else:
                    # Nested: expand when all children have results
                    if (
                        isinstance(src, DynamicFanOut)
                        and src._expanded
                        and all(child.name in results for child in src)
                    ):
                        ready_to_expand = True
                if ready_to_expand:
                    # Derive nested source value: collect each child result into a list
                    if isinstance(src, TaskInvocation):
                        source_value = results[src.name]
                    else:
                        source_value = [results[c.name] for c in src]
                    if not isinstance(source_value, (list, tuple, set)):
                        raise TaskExecutionError(
                            getattr(src, "task_name", "dynamic"),
                            RuntimeError("Dynamic fan_out source must return an iterable"),
                        )
                    placeholder.expand(source_value)
                    for child_inv in placeholder:
                        if child_inv.name not in dag.nodes:
                            dag.add_node(child_inv.name)
                        # Edge from all upstream of src's children or src itself
                        if isinstance(src, TaskInvocation):
                            dag.add_edge(src.name, child_inv.name)
                            # Source already finished, so dependency is satisfied immediately
                            remaining_deps[child_inv.name] = set()
                            ready.append(child_inv.name)
                        else:
                            # depend on all children of src
                            deps = {c.name for c in src}
                            for d in deps:
                                dag.add_edge(d, child_inv.name)
                            # All deps completed (readiness condition); mark none remaining
                            remaining_deps[child_inv.name] = set()
                            ready.append(child_inv.name)
                        # ensure inv_map aware
                        if child_inv.name not in inv_map:
                            inv_map[child_inv.name] = child_inv
                    # Update consumers
                    for consumer in invocations:
                        if consumer is src:
                            continue
                        replaced = False

                        def _walk(o, target=placeholder):  # bind loop var
                            nonlocal replaced
                            if o is target:
                                replaced = True
                                return list(target)
                            if isinstance(o, list):
                                return [_walk(x, target) for x in o]
                            if isinstance(o, tuple):
                                return tuple(_walk(x, target) for x in o)
                            if isinstance(o, dict):
                                return {k: _walk(v, target) for k, v in o.items()}
                            return o

                        consumer.args = (
                            _walk(list(consumer.args)) if consumer.args else consumer.args
                        )
                        consumer.kwargs = (
                            _walk(consumer.kwargs) if consumer.kwargs else consumer.kwargs
                        )
                        if replaced:
                            for child_inv in placeholder:
                                dag.add_edge(child_inv.name, consumer.name)
                                remaining_deps.setdefault(consumer.name, set()).add(child_inv.name)
                    # Placeholders remain for nested detection; do not delete
            # update downstream readiness
            # Use set() to guard against duplicate edges causing repeated scheduling attempts
            for child in set(dag.nodes[fname].downstream):
                remaining_deps[child].discard(fname)
                # Skip scheduling if any upstream failed and policy is not CONTINUE
                upstream_failed = any(
                    isinstance(results.get(up), TaskExecutionError)
                    for up in dag.nodes[child].upstream
                    if up in results
                )
                if upstream_failed and failure_policy != FailurePolicy.CONTINUE:
                    results[child] = TaskExecutionError(child, RuntimeError("Upstream failed"))
                    continue
                if (
                    not remaining_deps[child]
                    and child not in ready
                    and child not in pending_tasks
                    and child not in results
                ):
                    ready.append(child)
    if failure_policy == FailurePolicy.AGGREGATE and task_errors:
        raise AggregateTaskError(task_errors)
    return results


def _hydrate(struct: Any, results: dict[str, Any]) -> Any:
    from .build import TaskInvocation

    if isinstance(struct, TaskInvocation):
        return results[struct.name]
    if isinstance(struct, list):
        return [_hydrate(s, results) for s in struct]
    if isinstance(struct, tuple):
        return tuple(_hydrate(s, results) for s in struct)
    if isinstance(struct, set):
        return {_hydrate(s, results) for s in struct}
    if isinstance(struct, dict):
        return {k: _hydrate(v, results) for k, v in struct.items()}
    return struct
